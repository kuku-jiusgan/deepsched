from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from app.models import Task, Instrument, TimeSlot, Project, TaskDependency, InstrumentCapability, TaskCapabilityRequirement, MaintenanceWindow, InstrumentFault, Milestone
from app.schemas.schemas import InsertOrderRequest, InsertOrderCost, RescheduleRequest

TIME_UNIT_MINUTES = 30
HORIZON_DAYS = 90


class SchedulerService:
    def __init__(self, db: Session):
        self.db = db

    # ── Public API ──────────────────────────────────────────────

    def generate(self, project_ids: Optional[List[int]] = None) -> dict:
        tasks, instruments = self._load_data(project_ids)
        if not tasks:
            return {"status": "ok", "message": "没有待排仪器任务", "timeslots_created": 0}
        if not instruments:
            return {"status": "error", "message": "没有可用仪器"}

        horizon_start, horizon_end, total_units = self._time_horizon()
        compat = self._build_compatibility(tasks, instruments)
        task_deps = self._build_dependencies(tasks)
        maint_windows = self._build_maintenance_windows(instruments, horizon_start)

        model = cp_model.CpModel()

        # Decision variables
        intervals: Dict[Tuple[int, int], cp_model.IntervalVar] = {}
        presences: Dict[Tuple[int, int], cp_model.IntVar] = {}
        task_starts: Dict[int, cp_model.IntVar] = {}
        task_ends: Dict[int, cp_model.IntVar] = {}
        task_tardiness: Dict[int, cp_model.IntVar] = {}

        for t in tasks:
            dur = self._to_units(t.est_duration_hours or 4) + self._to_units(t.switchover_hours or 0)
            task_starts[t.id] = model.NewIntVar(0, total_units, f"start_t{t.id}")
            task_ends[t.id] = model.NewIntVar(0, total_units, f"end_t{t.id}")
            task_tardiness[t.id] = model.NewIntVar(0, total_units, f"tardy_t{t.id}")

            task_interval = model.NewIntervalVar(
                task_starts[t.id], dur, task_ends[t.id], f"task_iv_t{t.id}"
            )

            candidates = compat.get(t.id, [])
            if not candidates:
                continue

            alt_starts = []
            alt_ends = []
            alt_presences = []
            for inst in candidates:
                key = (t.id, inst.id)
                presences[key] = model.NewBoolVar(f"presence_t{t.id}_i{inst.id}")
                inst_start = model.NewIntVar(0, total_units, f"start_t{t.id}_i{inst.id}")
                inst_end = model.NewIntVar(0, total_units, f"end_t{t.id}_i{inst.id}")
                inst_iv = model.NewOptionalIntervalVar(
                    inst_start, dur, inst_end, presences[key], f"iv_t{t.id}_i{inst.id}"
                )
                intervals[key] = inst_iv
                alt_starts.append(inst_start)
                alt_ends.append(inst_end)
                alt_presences.append(presences[key])

                # Link per-instrument start to task start
                model.Add(inst_start == task_starts[t.id]).OnlyEnforceIf(presences[key])

            # Exactly one instrument assigned
            model.AddExactlyOne(alt_presences)

        # No-overlap per instrument
        for inst in instruments:
            inst_ivs = [intervals[k] for k in intervals if k[1] == inst.id]
            if inst_ivs:
                model.AddNoOverlap(inst_ivs)

        # Maintenance windows block instruments
        for inst_id, (mw_start, mw_end) in maint_windows:
            for (tid, iid), iv in intervals.items():
                if iid == inst_id:
                    # Task must end before maintenance OR start after maintenance
                    b_before = model.NewBoolVar(f"mw_before_t{tid}_i{iid}")
                    b_after = model.NewBoolVar(f"mw_after_t{tid}_i{iid}")
                    model.Add(task_ends[tid] <= mw_start).OnlyEnforceIf(b_before)
                    model.Add(task_starts[tid] >= mw_end).OnlyEnforceIf(b_after)
                    model.AddBoolOr([b_before, b_after])

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

        # Objective: minimize weighted tardiness + makespan
        weighted_tardy = []
        for t in tasks:
            w = int(t.priority_weight * 10)
            weighted_tardy.append(task_tardiness[t.id] * w)
        makespan = model.NewIntVar(0, total_units, "makespan")
        model.AddMaxEquality(makespan, [task_ends[t.id] for t in tasks])
        model.Minimize(sum(weighted_tardy) + makespan)

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {"status": "error", "message": "排程求解失败，请检查约束是否冲突"}

        # Persist results
        self._clear_slots()
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
            Task.requires_instrument == True,
            Task.status.in_(["pending", "ready"]),
        )
        if project_ids:
            q = q.filter(Task.project_id.in_(project_ids))
        tasks = q.order_by(Task.priority_weight.desc()).all()
        instruments = self.db.query(Instrument).filter(Instrument.status.in_(["active"])).all()
        return tasks, instruments

    def _time_horizon(self):
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
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

    def _clear_slots(self):
        self.db.query(TimeSlot).filter(
            TimeSlot.tier.in_(["forecast", "confirmed"])
        ).delete()

    def _persist_slots(self, tasks, instruments, solver, task_starts, task_ends, presences, horizon_start):
        now = datetime.now()
        frozen_boundary = now + timedelta(days=3)
        confirmed_boundary = now + timedelta(days=14)
        created = 0

        for t in tasks:
            assigned_inst = None
            for inst in instruments:
                key = (t.id, inst.id)
                if key in presences and solver.Value(presences[key]) == 1:
                    assigned_inst = inst
                    break
            if assigned_inst is None:
                continue

            start = self._units_to_datetime(solver.Value(task_starts[t.id]), horizon_start)
            end = self._units_to_datetime(solver.Value(task_ends[t.id]), horizon_start)

            if start <= frozen_boundary:
                tier = "frozen"
            elif start <= confirmed_boundary:
                tier = "confirmed"
            else:
                tier = "forecast"

            slot = TimeSlot(
                task_id=t.id,
                instrument_id=assigned_inst.id,
                plan_start=start,
                plan_end=end,
                tier=tier,
                status="scheduled",
            )
            self.db.add(slot)
            t.status = "scheduled"
            created += 1

        self.db.commit()
        return created

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
