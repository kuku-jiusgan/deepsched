from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from app.models import Instrument, Task, TimeSlot
from app.models.models import SysCalendar
from app.core.config import get_settings
from app.schemas.schemas import InsertOrderRequest, InsertOrderCost, RescheduleRequest
from app.services.schedule_rule_service import get_solver_constraints
from app.services.scheduler_persistence import persist_slots
from app.services.scheduler_helpers import (
    build_compatibility,
    build_dependencies,
    build_maintenance_windows,
    build_working_prefix_sum,
    datetime_to_units,
    time_horizon,
    to_units,
    working_time_bounds,
)


class SchedulerService:
    def __init__(self, db: Session):
        self.db = db

    # ── Public API ──────────────────────────────────────────────

    def generate(self, project_ids: Optional[List[int]] = None) -> dict:
        # Clear old slots and reset task statuses BEFORE loading
        self._clear_slots()
        tasks, instruments = self._load_data(project_ids)
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
        calendar_days = self._load_calendar_days(horizon_start, horizon_end)
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
        intervals: Dict[Tuple[int, int], cp_model.IntervalVar] = {}
        presences: Dict[Tuple[int, int], cp_model.IntVar] = {}
        inst_starts: Dict[Tuple[int, int], cp_model.IntVar] = {}
        inst_ends: Dict[Tuple[int, int], cp_model.IntVar] = {}
        task_starts: Dict[int, cp_model.IntVar] = {}
        task_ends: Dict[int, cp_model.IntVar] = {}
        task_tardiness: Dict[int, cp_model.IntVar] = {}

        for t in tasks:
            dur = to_units(t.est_duration_hours or 4) + to_units(t.switchover_hours or 0)

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
                intervals[key] = inst_iv
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
        # No-overlap per instrument
        # Bug 3 fix: frozen slots as immovable interval bricks (NOT via prefix-sum)
        frozen_slots = self.db.query(TimeSlot).filter(TimeSlot.tier == "frozen").all()

        for inst in instruments:
            inst_ivs = [intervals[k] for k in intervals if k[1] == inst.id]

            for slot in frozen_slots:
                if slot.instrument_id == inst.id:
                    f_start = max(0, datetime_to_units(slot.plan_start, horizon_start))
                    f_end = datetime_to_units(slot.plan_end, horizon_start)
                    if f_end > f_start:
                        fixed_iv = model.NewIntervalVar(f_start, f_end - f_start, f_end, f"froz_{slot.id}")
                        inst_ivs.append(fixed_iv)

            if inst_ivs and constraints["non_overlap"].is_enabled:
                model.AddNoOverlap(inst_ivs)
        # === Cross-project switching: setup time + penalty === (DISABLED FOR DEBUG)
        # === Cross-project switching: setup time + penalty ===
        setup_rule = constraints["cross_project_setup"]
        setup_hours = (
            (setup_rule.params or {}).get("setup_hours", 2)
            if setup_rule.is_enabled
            else 0
        )
        CROSS_PROJECT_SETUP_UNITS = to_units(setup_hours) if setup_hours else 0
        switch_penalties = []
        tasks_by_id = {t.id: t for t in tasks}

        for inst in instruments:
            inst_task_ids = [k[0] for k in intervals if k[1] == inst.id]
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

        # Objective: minimize weighted tardiness + makespan + span + switch + split penalties
        weighted_tardy = []
        for t in tasks:
            w = int(t.priority_weight * 10)
            weighted_tardy.append(task_tardiness[t.id] * w)
        makespan = model.NewIntVar(0, total_units, "makespan")
        model.AddMaxEquality(makespan, [task_ends[t.id] for t in tasks])

        spans = [task_ends[t.id] - task_starts[t.id] for t in tasks]
        weight_main = 1000
        weight_span = 1
        weight_switch = 500
        weight_split = 30   #这是同一台仪器跑用一个项目的惩罚系数  越高越不会切换
        model.Minimize(
            (sum(weighted_tardy) + makespan) * weight_main
            + sum(spans) * weight_span
            + sum(switch_penalties) * weight_switch
            + sum(project_inst_used_vars) * weight_split
        )

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        total_req_hours = sum(t.est_duration_hours or 4 for t in tasks if t.requires_instrument)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {"status": "error", "message": f"时间配置冲突：当前待排总工时约 {total_req_hours} 小时，请调整【项目开始/结束时间】或修改【项目工时】。"}

        # Persist results
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
        )

        return {
            "status": "ok",
            "message": f"排程完成，创建 {created} 个时间槽",
            "timeslots_created": created,
            "solver_status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "objective_value": int(solver.ObjectiveValue()),
        }

    def reschedule(self, data: RescheduleRequest) -> dict:
        if data.strategy == "local":
            return self._local_repair(data)
        elif data.strategy == "project":
            return self._project_reschedule(data)
        else:
            return self._global_reschedule(data)

    def complete_and_shift(self, task_id: int, actual_end_time = None) -> dict:
        """Early completion: truncate slots and trigger forward shift of dependent tasks."""
        now = datetime.now()
        end_time = actual_end_time or now

        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"status": "error", "message": "未找到指定任务"}

        task.status = "done"

        # Delete all future slots for this task
        self.db.query(TimeSlot).filter(
            TimeSlot.task_id == task_id,
            TimeSlot.plan_end > end_time
        ).delete(synchronize_session=False)

        # Truncate the ongoing slot that spans across end_time
        ongoing_slot = self.db.query(TimeSlot).filter(
            TimeSlot.task_id == task_id,
            TimeSlot.plan_start <= end_time,
            TimeSlot.plan_end > end_time
        ).first()
        if ongoing_slot:
            ongoing_slot.plan_end = end_time
            ongoing_slot.actual_end = end_time
            ongoing_slot.status = "completed"

        self.db.commit()
        return self._forward_shift_reschedule(task)

    def _forward_shift_reschedule(self, completed_task) -> dict:
        """Forward-shift: clear future slots of same-project and same-instrument tasks."""
        last_slot = self.db.query(TimeSlot).filter(
            TimeSlot.task_id == completed_task.id
        ).order_by(TimeSlot.plan_end.desc()).first()
        instrument_id = last_slot.instrument_id if last_slot else None

        # Scope 1: same-project scheduled tasks
        project_task_ids = self.db.query(Task.id).filter(
            Task.project_id == completed_task.project_id,
            Task.status == "scheduled"
        )

        # Scope 2: same-instrument tasks from other projects
        inst_task_ids = []
        if instrument_id:
            inst_task_ids = self.db.query(TimeSlot.task_id).filter(
                TimeSlot.instrument_id == instrument_id,
                TimeSlot.tier.in_(["confirmed", "forecast"]),
                TimeSlot.plan_start >= datetime.now()
            ).distinct()

        if inst_task_ids:
            affected = project_task_ids.union(inst_task_ids).subquery()
        else:
            affected = project_task_ids.subquery()

        self.db.query(TimeSlot).filter(
            TimeSlot.task_id.in_(affected),
            TimeSlot.tier.in_(["confirmed", "forecast"])
        ).delete(synchronize_session=False)

        self.db.query(Task).filter(
            Task.id.in_(affected),
            Task.status == "scheduled"
        ).update({"status": "pending"}, synchronize_session=False)

        self.db.commit()
        return self.generate()

    def calculate_insert_cost(self, data: InsertOrderRequest) -> InsertOrderCost:
        tasks = self.db.query(Task).filter(Task.id.in_(data.task_ids)).all()
        if not tasks:
            return InsertOrderCost()

        total_hours = sum(t.est_duration_hours or 4 for t in tasks)
        now = datetime.now()
        affected_slots = (
            self.db.query(TimeSlot)
            .filter(
                TimeSlot.tier == "confirmed",
                TimeSlot.status == "scheduled",
                TimeSlot.plan_start >= now,
            )
            .order_by(TimeSlot.plan_start)
            .limit(20)
            .all()
        )

        displaced = []
        affected_projects = set()
        milestone_violations = []
        total_delay = 0.0

        for slot in affected_slots:
            delay = total_hours * 0.5
            total_delay += delay
            displaced.append({
                "task_id": slot.task_id,
                "task_name": slot.task_name or "",
                "project_name": slot.project_name or "",
                "original_start": slot.plan_start.isoformat() if slot.plan_start else "",
                "delay_hours": round(delay, 1),
            })
            if slot.task and slot.task.project:
                affected_projects.add(slot.task.project.name)

        return InsertOrderCost(
            displaced_tasks=displaced,
            affected_projects=[{"name": n} for n in affected_projects],
            milestone_violations=milestone_violations,
            total_delay_hours=round(total_delay, 1),
        )

    # ── Private helpers ─────────────────────────────────────────

    def _load_data(self, project_ids):
        # Load leaf tasks only: tasks that have NO children (actual execution nodes)
        from sqlalchemy import not_

        sub_query = self.db.query(Task.parent_id).filter(Task.parent_id != None).subquery()

        q = self.db.query(Task).filter(
            Task.status.in_(["pending", "ready"]),
            not_(Task.id.in_(sub_query)),
        ).options(
            selectinload(Task.project),
            selectinload(Task.milestone),
            selectinload(Task.predecessors),
            selectinload(Task.capability_requirements),
        )
        if project_ids:
            q = q.filter(Task.project_id.in_(project_ids))
        tasks = q.order_by(Task.priority_weight.desc()).all()

        instruments = self.db.query(Instrument).filter(
            Instrument.status.in_(["idle", "running"])
        ).options(
            selectinload(Instrument.capabilities),
            selectinload(Instrument.maintenance_windows),
        ).all()
        return tasks, instruments

                # 不工作时间配置大于8点小于20点
    def _load_calendar_days(self, horizon_start: datetime, horizon_end: datetime) -> dict:
        rows = self.db.query(SysCalendar).filter(
            SysCalendar.date >= horizon_start.date(),
            SysCalendar.date <= horizon_end.date(),
        ).all()
        return {
            row.date: {
                "is_working_day": row.is_working_day,
                "day_type": row.day_type,
            }
            for row in rows
        }

    def _clear_slots(self):
        # Find tasks that have frozen time slots (must NOT be reset)
        frozen_task_ids = self.db.query(TimeSlot.task_id).filter(
            TimeSlot.tier == "frozen"
        ).distinct()

        # Also preserve completed/done task slots (historical record)
        done_task_ids = self.db.query(Task.id).filter(Task.status == "done").distinct()

        # Clear only forecast and confirmed tiers; preserve frozen + done history
        self.db.query(TimeSlot).filter(
            TimeSlot.tier.in_(["forecast", "confirmed"]),
            ~TimeSlot.task_id.in_(frozen_task_ids),
            ~TimeSlot.task_id.in_(done_task_ids),
        ).delete(synchronize_session=False)

        # Reset non-frozen, non-done tasks to pending
        self.db.query(Task).filter(
            Task.status.in_(["scheduled", "blocked"]),
            ~Task.id.in_(frozen_task_ids),
        ).update({"status": "pending"}, synchronize_session=False)

        self.db.commit()

    def _local_repair(self, data: RescheduleRequest) -> dict:
        if data.affected_task_id:
            task = self.db.query(Task).filter(Task.id == data.affected_task_id).first()
            if task:
                self.db.query(TimeSlot).filter(
                    TimeSlot.task_id == data.affected_task_id,
                    TimeSlot.tier.in_(["confirmed", "forecast"]),
                ).delete()
                task.status = "pending"
                self.db.commit()
        return self.generate()

    def _project_reschedule(self, data: RescheduleRequest) -> dict:
        if data.affected_task_id:
            task = self.db.query(Task).filter(Task.id == data.affected_task_id).first()
            if task:
                self.db.query(TimeSlot).filter(
                    TimeSlot.task_id.in_(
                        self.db.query(Task.id).filter(Task.project_id == task.project_id)
                    ),
                    TimeSlot.tier.in_(["confirmed", "forecast"]),
                ).delete()
                self.db.query(Task).filter(
                    Task.project_id == task.project_id,
                    Task.status == "scheduled",
                ).update({"status": "pending"})
                self.db.commit()
                return self.generate([task.project_id])
        return {"status": "error", "message": "未指定受影响任务"}

    def _global_reschedule(self, data: RescheduleRequest) -> dict:
        self.db.query(TimeSlot).filter(
            TimeSlot.tier.in_(["confirmed", "forecast"])
        ).delete()
        self.db.query(Task).filter(Task.status == "scheduled").update({"status": "pending"})
        self.db.commit()
        return self.generate()
