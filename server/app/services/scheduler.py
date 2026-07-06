from sqlalchemy.orm import Session, selectinload
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from app.models import Task, Instrument, TimeSlot, Project, TaskDependency, InstrumentCapability, TaskCapabilityRequirement, MaintenanceWindow, InstrumentFault, Milestone
from app.core.config import get_settings
from app.schemas.schemas import InsertOrderRequest, InsertOrderCost, RescheduleRequest

TIME_UNIT_MINUTES = 30
HORIZON_DAYS = 90


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

        horizon_start, horizon_end, total_units = self._time_horizon()
        compat = self._build_compatibility(tasks, instruments)
        task_deps = self._build_dependencies(tasks)
        maint_windows = self._build_maintenance_windows(instruments, horizon_start)
        global_prefix_sum = self._build_working_prefix_sum(horizon_start, total_units, maint_windows)

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
            dur = self._to_units(t.est_duration_hours or 4) + self._to_units(t.switchover_hours or 0)

            # Compute project-level hard constraint window
            p_start_unit = 0
            p_end_unit = total_units
            if t.project:
                if t.project.start_date:
                    p_start_u = self._datetime_to_units(t.project.start_date, horizon_start)
                    p_start_unit = max(0, p_start_u)
                if t.project.end_date:
                    p_end_u = self._datetime_to_units(t.project.end_date, horizon_start)
                    p_end_unit = min(total_units, p_end_u)

            # Guard: task duration exceeds available project window
            if p_start_unit + dur > p_end_unit:
                return {"status": "error", "message": f"排程失败：项目【{t.project.name if t.project else chr(39)+chr(39)}】的时间窗口过短，无法容纳任务【{t.name}】。"}

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
        for inst in instruments:
            inst_ivs = [intervals[k] for k in intervals if k[1] == inst.id]
            if inst_ivs:
                model.AddNoOverlap(inst_ivs)

        # === Cross-project switching: setup time + penalty === (DISABLED FOR DEBUG)
        # === Cross-project switching: setup time + penalty ===
        CROSS_PROJECT_SETUP_HOURS = 2.0
        CROSS_PROJECT_SETUP_UNITS = self._to_units(CROSS_PROJECT_SETUP_HOURS)
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
        for tid, pred_id in task_deps:
            if pred_id in task_starts and tid in task_starts:
                model.Add(task_starts[tid] >= task_ends[pred_id])

        # Milestone deadlines → tardiness
        for t in tasks:
            if t.milestone_id and t.milestone:
                deadline = self._datetime_to_units(t.milestone.due_date, horizon_start)
                if 0 <= deadline <= total_units:
                    model.Add(task_tardiness[t.id] >= task_ends[t.id] - deadline)

        # Objective: minimize weighted tardiness + makespan + span penalty
        weighted_tardy = []
        for t in tasks:
            w = int(t.priority_weight * 10)
            weighted_tardy.append(task_tardiness[t.id] * w)
        makespan = model.NewIntVar(0, total_units, "makespan")
        model.AddMaxEquality(makespan, [task_ends[t.id] for t in tasks])

        # Span penalty: encourage compact spans, avoid unnecessary night gaps
        spans = [task_ends[t.id] - task_starts[t.id] for t in tasks]
        weight_main = 1000
        weight_span = 1
        weight_switch = 500
        model.Minimize(
            (sum(weighted_tardy) + makespan) * weight_main
            + sum(spans) * weight_span
            + sum(switch_penalties) * weight_switch
        )

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        total_req_hours = sum(t.est_duration_hours or 4 for t in tasks if t.requires_instrument)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {"status": "error", "message": f"排程求解失败（无解）。本次待排总工时约 {total_req_hours} 小时，可能由于某些项目的截止时间过于紧迫，或者仪器在所需时间段内被维保/夜间窗口锁死导致资源不足。"}

        # Persist results
        created = self._persist_slots(
            tasks, instruments, solver, task_starts, task_ends, presences, horizon_start
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
        q = self.db.query(Task).filter(
            Task.status.in_(["pending", "ready"]),
            Task.parent_id == None,
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

    def _time_horizon(self):
        now = datetime.now().replace(second=0, microsecond=0)
        # Round up to next 30-min slot
        m = now.minute
        if m % 30 != 0:
            m = ((m // 30) + 1) * 30
            if m >= 60:
                now = now.replace(hour=now.hour + 1, minute=0)
            else:
                now = now.replace(minute=m)
        horizon_start = now
        horizon_end = now + timedelta(days=HORIZON_DAYS)
        total_units = int((horizon_end - horizon_start).total_seconds() / 60 / TIME_UNIT_MINUTES)
        return horizon_start, horizon_end, total_units

    def _to_units(self, hours: float) -> int:
        return max(1, int(hours * 60 / TIME_UNIT_MINUTES))

    def _datetime_to_units(self, dt: datetime, horizon_start: datetime) -> int:
        return int((dt - horizon_start).total_seconds() / 60 / TIME_UNIT_MINUTES)

    def _units_to_datetime(self, units: int, horizon_start: datetime) -> datetime:
        return horizon_start + timedelta(minutes=units * TIME_UNIT_MINUTES)

    def _build_compatibility(self, tasks, instruments):
        compat: Dict[int, List[Instrument]] = {}
        for t in tasks:
            if not t.requires_instrument:
                compat[t.id] = []
                continue
            # Use instrument_ids if set, otherwise fall back to capability matching
            inst_ids_raw = t.instrument_ids if hasattr(t, 'instrument_ids') and t.instrument_ids else None
            if inst_ids_raw:
                # Normalize: JSON column may return string or list depending on DB backend
                if isinstance(inst_ids_raw, str):
                    import json as _json
                    try:
                        inst_ids = _json.loads(inst_ids_raw)
                    except (_json.JSONDecodeError, ValueError):
                        inst_ids = [int(x.strip()) for x in inst_ids_raw.split(',') if x.strip()]
                elif isinstance(inst_ids_raw, list):
                    inst_ids = [int(x) for x in inst_ids_raw]
                else:
                    inst_ids = [int(inst_ids_raw)]
                compat[t.id] = [inst for inst in instruments if inst.id in inst_ids]
            else:
                reqs = t.capability_requirements
                if not reqs:
                    compat[t.id] = list(instruments)
                    continue
                matched = []
                for inst in instruments:
                    inst_caps = {(c.tag_name, c.tag_value) for c in inst.capabilities}
                    req_set = {(r.tag_name, r.tag_value) for r in reqs}
                    if req_set.issubset(inst_caps):
                        matched.append(inst)
                compat[t.id] = matched
        return compat

    def _build_dependencies(self, tasks):
        task_ids = {t.id for t in tasks}
        deps = []
        for t in tasks:
            for dep in t.predecessors:
                if dep.predecessor_id in task_ids:
                    deps.append((t.id, dep.predecessor_id))
        return deps

    def _build_maintenance_windows(self, instruments, horizon_start):
        windows = []
        for inst in instruments:
            for mw in inst.maintenance_windows:
                start_u = self._datetime_to_units(mw.start_time, horizon_start)
                end_u = self._datetime_to_units(mw.end_time, horizon_start)
                if end_u > 0:
                    windows.append((inst.id, (max(0, start_u), end_u)))
        return windows


    def _build_working_prefix_sum(self, horizon_start, total_units, maint_windows=None):
        """Generate a prefix-sum array mapping physical time slots to cumulative working slots.
        prefix_sum[t] = number of working slots in [0, t)."""
        is_working = [1] * total_units

                # Apply global night-window: non-working 20:00-08:00
        for i in range(total_units):
            dt = horizon_start + timedelta(minutes=i * TIME_UNIT_MINUTES)
            if dt.hour < 8 or dt.hour >= 20:
                is_working[i] = 0

        # Mark maintenance windows as non-working too
        if maint_windows:
            for inst_id, (mw_start, mw_end) in maint_windows:
                for i in range(max(0, mw_start), min(mw_end, total_units)):
                    is_working[i] = 0

        prefix_sum = [0] * (total_units + 1)
        for i in range(total_units):
            prefix_sum[i + 1] = prefix_sum[i] + is_working[i]

        return prefix_sum

    def _clear_slots(self):
        # Clear ALL non-frozen old slots, and reset task statuses
        self.db.query(TimeSlot).delete()
        self.db.query(Task).filter(
            Task.status.in_(["scheduled", "blocked"])
        ).update({"status": "pending"})

    def _persist_slots(self, tasks, instruments, solver, task_starts, task_ends, presences, horizon_start):
        now = datetime.now()
        frozen_boundary = now + timedelta(days=get_settings().FROZEN_DAYS)
        confirmed_boundary = now + timedelta(days=get_settings().CONFIRMED_DAYS)
        created = 0

        for t in tasks:
            assigned_inst = None
            if t.requires_instrument:
                for inst in instruments:
                    key = (t.id, inst.id)
                    if key in presences and solver.Value(presences[key]) == 1:
                        assigned_inst = inst
                        break
                if assigned_inst is None:
                    continue

            start_unit = solver.Value(task_starts[t.id])
            end_unit = solver.Value(task_ends[t.id])

            # Split physical span into working chunks, skipping night windows
            chunk_start = None
            for i in range(start_unit, end_unit):
                dt = horizon_start + timedelta(minutes=i * TIME_UNIT_MINUTES)
                is_work = (8 <= dt.hour < 20)

                if is_work and chunk_start is None:
                    chunk_start = dt
                elif not is_work and chunk_start is not None:
                    chunk_end = dt
                    self._create_db_slot(t, assigned_inst, chunk_start, chunk_end, frozen_boundary, confirmed_boundary)
                    created += 1
                    chunk_start = None

            # Close any remaining open chunk
            if chunk_start is not None:
                final_end = horizon_start + timedelta(minutes=end_unit * TIME_UNIT_MINUTES)
                self._create_db_slot(t, assigned_inst, chunk_start, final_end, frozen_boundary, confirmed_boundary)
                created += 1

            t.status = "scheduled"

        self.db.commit()
        return created

    def _create_db_slot(self, task, inst, start, end, frozen_boundary, confirmed_boundary):
        if start <= frozen_boundary:
            tier = "frozen"
        elif start <= confirmed_boundary:
            tier = "confirmed"
        else:
            tier = "forecast"

        slot = TimeSlot(
            task_id=task.id,
            instrument_id=inst.id if inst else None,
            plan_start=start,
            plan_end=end,
            tier=tier,
            status="scheduled",
        )
        self.db.add(slot)

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
