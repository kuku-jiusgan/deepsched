from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from uuid import uuid4
from ortools.sat.python import cp_model
from app.models import Task, TimeSlot
from app.core.config import get_settings
from app.services.schedule_rule_service import get_solver_constraints
from app.services.schedule_conflict_service import ScheduleConflictError, ensure_no_instrument_conflicts
from app.services.scheduler_fixed_slots import add_instrument_capacity_constraints, load_fixed_slots
from app.services.scheduler_persistence import persist_slots
from app.services.scheduler_objective import add_scheduler_objective
from app.services.scheduler_split_tasks import add_split_task_variables
from app.services.scheduler_diagnostics import frozen_schedule_message, unavailable_instrument_message
from app.services.scheduler_data import load_scheduler_data
from app.services.scheduler_helpers import (
    build_compatibility,
    build_dependencies,
    build_maintenance_windows,
    build_working_prefix_sum,
    datetime_to_units,
    load_calendar_days,
    time_horizon,
    to_units,
    working_time_bounds,
)


class SchedulerService:
    def __init__(self, db: Session):
        self.db = db

    def generate(
        self,
        project_ids: Optional[List[int]] = None,
        mode: str = "normal",
        task_ids: Optional[List[int]] = None,
        commit: bool = True,
    ) -> dict:
        tasks, instruments = load_scheduler_data(self.db, project_ids, task_ids)
        if not tasks:
            return {"status": "ok", "message": "没有待排仪器任务", "timeslots_created": 0}
        if not instruments:
            return {"status": "error", "message": "没有可用仪器"}

        constraints = get_solver_constraints(self.db)
        horizon_start, horizon_end, total_units = time_horizon()

        freezing_rule = constraints["freezing"]
        freeze_days = (freezing_rule.params or {}).get(
            "freeze_days",
            get_settings().FROZEN_DAYS,
        )

        compat = build_compatibility(
            tasks,
            instruments,
            constraints["capability_matching"].is_enabled,
        )
        diagnostic_message = unavailable_instrument_message(self.db, tasks, compat)
        if diagnostic_message:
            return {"status": "error", "message": diagnostic_message}

        task_deps = build_dependencies(tasks)
        maintenance_rule = constraints["maintenance_avoidance"]
        maint_windows = (
            build_maintenance_windows(instruments, horizon_start)
            if maintenance_rule.is_enabled
            else []
        )
        working_rule = constraints["working_hours"]
        working_params = working_rule.params or {}
        day_start_minutes, day_end_minutes = working_time_bounds(working_params)
        include_weekends = bool(working_params.get("include_weekends", False))
        include_holidays = bool(working_params.get("include_holidays", False))
        if not working_rule.is_enabled:
            day_start_minutes, day_end_minutes = 0, 24 * 60
            include_weekends, include_holidays = True, True
        calendar_days = load_calendar_days(self.db, horizon_start, horizon_end)
        global_prefix_sum = build_working_prefix_sum(
            horizon_start,
            total_units,
            day_start_minutes,
            day_end_minutes,
            maint_windows,
            calendar_days,
            include_weekends,
            include_holidays,
        )

        model = cp_model.CpModel()

        # Decision variables
        capacity_intervals: Dict[int, list[cp_model.IntervalVar]] = {}
        presences: Dict[Tuple[int, int], cp_model.IntVar] = {}
        inst_starts: Dict[Tuple[int, int], cp_model.IntVar] = {}
        inst_ends: Dict[Tuple[int, int], cp_model.IntVar] = {}
        task_starts: Dict[int, cp_model.IntVar] = {}
        task_ends: Dict[int, cp_model.IntVar] = {}
        task_tardiness: Dict[int, cp_model.IntVar] = {}
        split_unit_presences: Dict[Tuple[int, int, int], cp_model.IntVar] = {}
        for instrument in instruments:
            capacity_intervals[instrument.id] = []

        for t in tasks:
            dur = to_units(t.est_duration_hours or 4)
            if t.switchover_hours and t.switchover_hours > 0:
                dur += to_units(t.switchover_hours)

            # Compute project-level hard constraint window
            p_start_unit = 0
            p_end_unit = total_units
            if t.project and constraints["project_window"].is_enabled:
                if t.project.start_date:
                    p_start_u = datetime_to_units(t.project.start_date, horizon_start)
                    p_start_unit = max(0, p_start_u)
                if t.project.end_date:
                    p_end_u = datetime_to_units(t.project.end_date, horizon_start)
                    p_end_unit = min(total_units, p_end_u)

            # Guard: task duration exceeds available project window
            if p_start_unit + dur > p_end_unit:
                return {"status": "error", "message": f"排程失败：项目【{t.project.name if t.project else chr(39)+chr(39)}】时间窗口不足。"}

            # Constrain task start/end within project boundaries
            task_starts[t.id] = model.NewIntVar(p_start_unit, p_end_unit, f"start_t{t.id}")
            task_ends[t.id] = model.NewIntVar(p_start_unit, p_end_unit, f"end_t{t.id}")
            task_tardiness[t.id] = model.NewIntVar(0, total_units, f"tardy_t{t.id}")

            # Physical span can stretch beyond dur to accommodate night breaks
            task_span = model.NewIntVar(dur, total_units, f"span_t{t.id}")
            model.Add(task_ends[t.id] - task_starts[t.id] == task_span)

            task_interval = model.NewIntervalVar(
                task_starts[t.id], task_span, task_ends[t.id], f"task_iv_t{t.id}"
            )

            candidates = compat.get(t.id, [])
            if not candidates:
                # Manual task: apply prefix-sum constraint to respect night window
                start_work_acc = model.NewIntVar(0, total_units, f"start_acc_t{t.id}")
                end_work_acc = model.NewIntVar(0, total_units, f"end_acc_t{t.id}")
                model.AddElement(task_starts[t.id], global_prefix_sum, start_work_acc)
                model.AddElement(task_ends[t.id], global_prefix_sum, end_work_acc)
                model.Add(end_work_acc - start_work_acc == dur)
                continue

            if t.allow_split:
                is_valid_split = add_split_task_variables(
                    model,
                    t,
                    candidates,
                    dur,
                    p_start_unit,
                    p_end_unit,
                    total_units,
                    global_prefix_sum,
                    task_starts[t.id],
                    task_ends[t.id],
                    presences,
                    inst_starts,
                    inst_ends,
                    capacity_intervals,
                    split_unit_presences,
                )
                if not is_valid_split:
                    return {"status": "error", "message": f"排程失败：任务【{t.name}】没有足够的可拆分工作时段。"}
                continue

            alt_starts = []
            alt_ends = []
            alt_presences = []
            for inst in candidates:
                key = (t.id, inst.id)
                presences[key] = model.NewBoolVar(f"presence_t{t.id}_i{inst.id}")
                inst_start = model.NewIntVar(0, total_units, f"start_t{t.id}_i{inst.id}")
                inst_end = model.NewIntVar(0, total_units, f"end_t{t.id}_i{inst.id}")
                inst_span = model.NewIntVar(0, total_units, f"span_t{t.id}_i{inst.id}")
                model.Add(inst_end - inst_start == inst_span)

                inst_iv = model.NewOptionalIntervalVar(
                    inst_start, inst_span, inst_end, presences[key], f"iv_t{t.id}_i{inst.id}"
                )
                capacity_intervals[inst.id].append(inst_iv)
                alt_starts.append(inst_start)
                alt_ends.append(inst_end)
                alt_presences.append(presences[key])

                # Store per-instrument start/end for cross-project constraints
                inst_starts[key] = inst_start
                inst_ends[key] = inst_end

                # Bidirectional link: per-instrument start/end == task start/end
                model.Add(task_starts[t.id] == inst_start).OnlyEnforceIf(presences[key])
                model.Add(task_ends[t.id] == inst_end).OnlyEnforceIf(presences[key])
                # When not selected, force instrument start/end to zero
                model.Add(inst_start == 0).OnlyEnforceIf(presences[key].Not())
                model.Add(inst_end == 0).OnlyEnforceIf(presences[key].Not())

                # Prefix-sum constraint: effective working time within span == dur
                start_work_acc = model.NewIntVar(0, total_units, f"start_acc_t{t.id}_i{inst.id}")
                end_work_acc = model.NewIntVar(0, total_units, f"end_acc_t{t.id}_i{inst.id}")
                model.AddElement(inst_start, global_prefix_sum, start_work_acc)
                model.AddElement(inst_end, global_prefix_sum, end_work_acc)
                model.Add(end_work_acc - start_work_acc == dur).OnlyEnforceIf(presences[key])

            # Exactly one instrument assigned
            model.AddExactlyOne(alt_presences)
        # === Cross-project switching: setup time + penalty ===
        setup_rule = constraints["cross_project_setup"]
        setup_hours = (
            (setup_rule.params or {}).get("setup_hours", 2)
            if setup_rule.is_enabled
            else 0
        )
        CROSS_PROJECT_SETUP_UNITS = to_units(setup_hours) if setup_hours else 0
        fixed_slots = load_fixed_slots(self.db, {task.id for task in tasks})
        add_instrument_capacity_constraints(
            model,
            instruments,
            tasks,
            capacity_intervals,
            presences,
            inst_starts,
            inst_ends,
            split_unit_presences,
            fixed_slots,
            horizon_start,
            total_units,
            constraints["non_overlap"].is_enabled,
            CROSS_PROJECT_SETUP_UNITS,
        )
        switch_penalties = []
        tasks_by_id = {t.id: t for t in tasks}

        for inst in instruments:
            inst_task_ids = [key[0] for key in presences if key[1] == inst.id]
            for i in range(len(inst_task_ids)):
                for j in range(i + 1, len(inst_task_ids)):
                    tA_id = inst_task_ids[i]
                    tB_id = inst_task_ids[j]
                    tA = tasks_by_id[tA_id]
                    tB = tasks_by_id[tB_id]

                    if tA.project_id == tB.project_id:
                        continue

                    pA = presences[(tA_id, inst.id)]
                    pB = presences[(tB_id, inst.id)]
                    startA, endA = inst_starts[(tA_id, inst.id)], inst_ends[(tA_id, inst.id)]
                    startB, endB = inst_starts[(tB_id, inst.id)], inst_ends[(tB_id, inst.id)]

                    a_before_b = model.NewBoolVar(f"seq_{tA_id}_before_{tB_id}_on_{inst.id}")
                    b_before_a = model.NewBoolVar(f"seq_{tB_id}_before_{tA_id}_on_{inst.id}")

                    # Ordering: when both present, exactly one precedes the other
                    model.Add(a_before_b + b_before_a == 1).OnlyEnforceIf([pA, pB])
                    # When not co-present, force ordering vars to 0
                    model.Add(a_before_b == 0).OnlyEnforceIf(pA.Not())
                    model.Add(b_before_a == 0).OnlyEnforceIf(pA.Not())
                    model.Add(a_before_b == 0).OnlyEnforceIf(pB.Not())
                    model.Add(b_before_a == 0).OnlyEnforceIf(pB.Not())

                    # Setup time between cross-project tasks
                    model.Add(startB >= endA + CROSS_PROJECT_SETUP_UNITS).OnlyEnforceIf([pA, pB, a_before_b])
                    model.Add(startA >= endB + CROSS_PROJECT_SETUP_UNITS).OnlyEnforceIf([pA, pB, b_before_a])

                    # Collect cross-project co-presence for penalty
                    both_present = model.NewBoolVar(f"both_{tA_id}_{tB_id}_on_{inst.id}")
                    
                    # Proper AND: both_present = pA AND pB
                    model.AddImplication(both_present, pA)
                    model.AddImplication(both_present, pB)
                    model.AddBoolOr([pA.Not(), pB.Not()]).OnlyEnforceIf(both_present.Not())
                    
                    switch_penalties.append(both_present)

        # Precedence constraints (DAG)
        # Bug 1 fix: handle frozen/missing predecessors as constant bounds
        missing_pred_ids = {pred_id for tid, pred_id in task_deps if pred_id not in task_starts}
        all_dep_pred_ids = {d.predecessor_id for t in tasks for d in t.predecessors}
        missing_pred_ids |= (all_dep_pred_ids - {t.id for t in tasks})

        missing_pred_ends = {}
        if missing_pred_ids:
            latest_slots = self.db.query(
                TimeSlot.task_id,
                func.max(TimeSlot.plan_end).label("max_end")
            ).filter(TimeSlot.task_id.in_(missing_pred_ids)).group_by(TimeSlot.task_id).all()
            for pid, max_end in latest_slots:
                if max_end:
                    missing_pred_ends[pid] = max(0, datetime_to_units(max_end, horizon_start))

        if constraints["precedence"].is_enabled:
            for tid, pred_id in task_deps:
                if pred_id in task_starts and tid in task_starts:
                    model.Add(task_starts[tid] >= task_ends[pred_id])

            # Frozen/missing predecessors: apply constant lower-bound
            for t in tasks:
                for dep in t.predecessors:
                    if dep.predecessor_id in missing_pred_ends and t.id in task_starts:
                        model.Add(task_starts[t.id] >= missing_pred_ends[dep.predecessor_id])

        # === Project split penalty: discourage spreading one project across many instruments ===
        project_to_tasks = {}
        for t in tasks:
            if t.requires_instrument and t.project_id:
                if t.project_id not in project_to_tasks:
                    project_to_tasks[t.project_id] = []
                project_to_tasks[t.project_id].append(t)

        project_inst_used_vars = []
        for pid, p_tasks in project_to_tasks.items():
            for inst in instruments:
                used_var = model.NewBoolVar(f"used_p{pid}_i{inst.id}")
                task_presences = []
                for t in p_tasks:
                    key = (t.id, inst.id)
                    if key in presences:
                        task_presences.append(presences[key])
                if task_presences:
                    model.AddMaxEquality(used_var, task_presences)
                    project_inst_used_vars.append(used_var)

        # Milestone deadlines → tardiness
        for t in tasks:
            if (
                constraints["milestone_deadline"].is_enabled
                and t.milestone_id
                and t.milestone
            ):
                deadline = datetime_to_units(t.milestone.due_date, horizon_start)
                if 0 <= deadline <= total_units:
                    model.Add(task_tardiness[t.id] >= task_ends[t.id] - deadline)

        add_scheduler_objective(
            model,
            tasks,
            task_starts,
            task_ends,
            task_tardiness,
            switch_penalties,
            project_inst_used_vars,
            total_units,
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        total_req_hours = sum(t.est_duration_hours or 4 for t in tasks if t.requires_instrument)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            frozen_message = (
                frozen_schedule_message(
                    tasks,
                    compat,
                    fixed_slots,
                    global_prefix_sum,
                    horizon_start,
                    total_units,
                    CROSS_PROJECT_SETUP_UNITS,
                )
                if status == cp_model.INFEASIBLE
                and constraints["non_overlap"].is_enabled
                else None
            )
            if frozen_message:
                return {"status": "error", "message": frozen_message}
            return {"status": "error", "message": f"时间配置冲突：当前待排总工时约 {total_req_hours} 小时，请调整【项目开始/结束时间】或修改【项目工时】。"}

        # Persist results
        schedule_run_id = _new_schedule_run_id()
        created = persist_slots(
            self.db,
            tasks,
            instruments,
            solver,
            task_starts,
            task_ends,
            presences,
            horizon_start,
            day_start_minutes,
            day_end_minutes,
            freeze_days,
            calendar_days,
            include_weekends,
            include_holidays,
            schedule_run_id,
            commit=False,
            split_unit_presences=split_unit_presences,
        )

        try:
            ensure_no_instrument_conflicts(self.db)
        except ScheduleConflictError as exc:
            self.db.rollback()
            return {"status": "error", "message": str(exc), "timeslots_created": 0}
        if commit:
            self.db.commit()

        return {
            "status": "ok",
            "message": f"排程完成，创建 {created} 个时间槽",
            "timeslots_created": created,
            "schedule_run_id": schedule_run_id,
            "solver_status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "objective_value": int(solver.ObjectiveValue()),
        }

def _new_schedule_run_id() -> str:
    return f"{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
