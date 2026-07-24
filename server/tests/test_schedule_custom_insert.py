import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, Task, TaskDependency, TimeSlot
from app.services.schedule_insert_service import (
    ScheduleInsertInvalidError,
    _add_custom_dependencies,
    _build_custom_insert_context,
)


class ScheduleCustomInsertTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.source_project = self._project("SRC")
        self.target_project = self._project("TGT")

    def tearDown(self):
        self.db.close()

    def _project(self, code: str) -> Project:
        project = Project(
            code=code,
            name=f"项目{code}",
            priority=3,
            end_date=datetime(2026, 8, 31, 18, 0),
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _task(self, project: Project, name: str, status: str = "scheduled") -> Task:
        task = Task(
            project_id=project.id,
            name=name,
            task_type="test",
            status=status,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _schedule(self, task: Task) -> None:
        self.db.add(TimeSlot(
            task_id=task.id,
            plan_start=datetime(2026, 8, 3, 8, 30),
            plan_end=datetime(2026, 8, 3, 12, 30),
            tier="confirmed",
            status="scheduled",
        ))
        self.db.flush()

    def test_custom_insert_connects_anchor_source_and_original_successor(self):
        anchor = self._task(self.target_project, "目标任务")
        target_next = self._task(self.target_project, "目标后续")
        source_first = self._task(self.source_project, "插入任务一")
        source_last = self._task(self.source_project, "插入任务二")
        self.db.add_all([
            TaskDependency(task_id=target_next.id, predecessor_id=anchor.id),
            TaskDependency(task_id=source_last.id, predecessor_id=source_first.id),
        ])
        self._schedule(anchor)

        context = _build_custom_insert_context(
            self.db,
            anchor.id,
            [source_first, source_last],
        )
        _add_custom_dependencies(self.db, context["dependency_pairs"])
        self.db.flush()

        pairs = {
            (item.task_id, item.predecessor_id)
            for item in self.db.query(TaskDependency).all()
        }
        self.assertIn((source_first.id, anchor.id), pairs)
        self.assertIn((target_next.id, source_last.id), pairs)
        self.assertEqual("inserted", context["impact_roles"][source_first.id])
        self.assertEqual("anchor_downstream", context["impact_roles"][target_next.id])

    def test_custom_insert_keeps_unselected_source_downstream_after_source(self):
        anchor = self._task(self.target_project, "目标方法开发")
        target_next = self._task(self.target_project, "目标后续")
        source = self._task(self.source_project, "方法开发")
        source_next = self._task(self.source_project, "验证")
        self.db.add_all([
            TaskDependency(task_id=target_next.id, predecessor_id=anchor.id),
            TaskDependency(task_id=source_next.id, predecessor_id=source.id),
        ])
        self._schedule(anchor)

        context = _build_custom_insert_context(self.db, anchor.id, [source])

        self.assertIn((source.id, anchor.id), context["dependency_pairs"])
        self.assertIn((target_next.id, source_next.id), context["dependency_pairs"])
        self.assertIn(source_next.id, {task.id for task in context["replan_tasks"]})

    def test_custom_insert_rejects_cycle(self):
        anchor = self._task(self.target_project, "目标任务")
        source = self._task(self.source_project, "插入任务")
        self.db.add(TaskDependency(task_id=anchor.id, predecessor_id=source.id))
        self._schedule(anchor)

        with self.assertRaisesRegex(ScheduleInsertInvalidError, "循环前置关系"):
            _build_custom_insert_context(self.db, anchor.id, [source])

    def test_repeated_custom_insert_accepts_existing_dependencies(self):
        anchor = self._task(self.target_project, "目标任务")
        source = self._task(self.source_project, "插入任务")
        self.db.add(TaskDependency(task_id=source.id, predecessor_id=anchor.id))
        self._schedule(anchor)
        self.db.flush()

        context = _build_custom_insert_context(self.db, anchor.id, [source])

        self.assertIn((source.id, anchor.id), context["dependency_pairs"])

    def test_custom_insert_rejects_completed_anchor_downstream(self):
        anchor = self._task(self.target_project, "目标任务")
        target_next = self._task(self.target_project, "已完成后续", status="completed")
        source = self._task(self.source_project, "插入任务")
        self.db.add(TaskDependency(task_id=target_next.id, predecessor_id=anchor.id))
        self._schedule(anchor)

        with self.assertRaisesRegex(ScheduleInsertInvalidError, "已开始或已完成"):
            _build_custom_insert_context(self.db, anchor.id, [source])

    def test_custom_insert_rejects_tasks_waiting_for_approval(self):
        anchor = self._task(self.target_project, "目标方法开发")
        source = self._task(self.source_project, "方法验证", status="waiting_external")
        self._schedule(anchor)

        with self.assertRaisesRegex(ScheduleInsertInvalidError, "仍受方案签批限制"):
            _build_custom_insert_context(self.db, anchor.id, [source])


if __name__ == "__main__":
    unittest.main()
