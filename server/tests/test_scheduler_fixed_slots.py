import unittest
from datetime import datetime
from types import SimpleNamespace

from ortools.sat.python import cp_model
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import TimeSlot
from app.services.scheduler_fixed_slots import (
    add_human_capacity_constraints,
    add_instrument_capacity_constraints,
    load_fixed_slots,
)


class SchedulerFixedSlotsTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_unexecuted_completed_segments_are_not_fixed(self):
        executed = TimeSlot(
            task_id=1, instrument_id=1,
            plan_start=datetime(2026, 7, 13, 8, 30),
            plan_end=datetime(2026, 7, 13, 20, 0),
            actual_start=datetime(2026, 7, 13, 8, 30),
            actual_end=datetime(2026, 7, 13, 12, 0),
            status="completed",
        )
        unexecuted = TimeSlot(
            task_id=1, instrument_id=1,
            plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 20, 0),
            status="completed",
        )
        scheduled = TimeSlot(
            task_id=2, instrument_id=1,
            plan_start=datetime(2026, 7, 15, 8, 30),
            plan_end=datetime(2026, 7, 15, 10, 0),
            status="scheduled",
        )
        self.db.add_all([executed, unexecuted, scheduled])
        self.db.commit()

        fixed_slots = load_fixed_slots(self.db)

        self.assertEqual({executed.id, scheduled.id}, {slot.id for slot in fixed_slots})

    def test_manual_task_slot_is_loaded_as_fixed(self):
        manual_slot = TimeSlot(
            task_id=1, instrument_id=None,
            plan_start=datetime(2026, 7, 15, 8, 30),
            plan_end=datetime(2026, 7, 15, 10, 0),
            status="scheduled",
        )
        self.db.add(manual_slot)
        self.db.commit()

        fixed_slots = load_fixed_slots(self.db)

        self.assertEqual([manual_slot.id], [slot.id for slot in fixed_slots])

    def test_human_tasks_for_same_assignee_cannot_overlap(self):
        model = cp_model.CpModel()
        first_start = model.NewIntVar(0, 2, "first_start")
        first_end = model.NewIntVar(2, 4, "first_end")
        second_start = model.NewIntVar(0, 2, "second_start")
        second_end = model.NewIntVar(2, 4, "second_end")
        first_interval = model.NewIntervalVar(first_start, 2, first_end, "first")
        second_interval = model.NewIntervalVar(second_start, 2, second_end, "second")
        tasks = [
            SimpleNamespace(id=1, requires_human=True, assignee_id=1),
            SimpleNamespace(id=2, requires_human=True, assignee_id=1),
        ]

        add_human_capacity_constraints(
            model,
            tasks,
            {1: first_interval, 2: second_interval},
            [],
            datetime(2026, 7, 14),
            4,
        )
        solver = cp_model.CpSolver()

        self.assertIn(solver.Solve(model), (cp_model.OPTIMAL, cp_model.FEASIBLE))
        self.assertTrue(
            solver.Value(first_end) <= solver.Value(second_start)
            or solver.Value(second_end) <= solver.Value(first_start)
        )

    def test_new_task_cannot_jump_a_frozen_instrument_slot(self):
        model = cp_model.CpModel()
        start = model.NewIntVar(0, 9, "start")
        end = model.NewIntVar(1, 10, "end")
        presence = model.NewBoolVar("presence")
        model.Add(presence == 1)
        model.Add(end == start + 1)
        interval = model.NewOptionalIntervalVar(start, 1, end, presence, "task")
        frozen_slot = TimeSlot(
            id=10,
            task_id=20,
            instrument_id=1,
            plan_start=datetime(2026, 7, 14, 9, 30),
            plan_end=datetime(2026, 7, 14, 10, 30),
            tier="frozen",
            status="scheduled",
        )

        add_instrument_capacity_constraints(
            model=model,
            instruments=[SimpleNamespace(id=1)],
            tasks=[SimpleNamespace(id=1, allow_split=False)],
            capacity_intervals={1: [interval]},
            presences={(1, 1): presence},
            inst_starts={(1, 1): start},
            inst_ends={(1, 1): end},
            split_unit_presences={},
            fixed_slots=[frozen_slot],
            horizon_start=datetime(2026, 7, 14, 8, 30),
            total_units=10,
            non_overlap_enabled=True,
            setup_units=0,
        )
        model.Minimize(start)
        solver = cp_model.CpSolver()

        self.assertEqual(cp_model.OPTIMAL, solver.Solve(model))
        self.assertEqual(4, solver.Value(start))


if __name__ == "__main__":
    unittest.main()
