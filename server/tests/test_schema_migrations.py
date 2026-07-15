import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.schema_migrations import ensure_runtime_schema
from app.models import Project, Task, User


class SchemaMigrationsTest(unittest.TestCase):
    def test_backfills_approval_gate_assignee_from_project_manager(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        manager = User(id=1, username="manager", display_name="负责人", role="分析员")
        project = Project(id=1, name="项目", code="P-001", manager_id=manager.id)
        gate = Task(
            id=1,
            project_id=project.id,
            name="方案签批",
            task_type="approval_gate",
            is_external_gate=True,
            assignee_id=None,
        )
        db.add_all([manager, project, gate])
        db.commit()

        ensure_runtime_schema(engine)
        db.expire_all()

        self.assertEqual(manager.id, db.get(Task, gate.id).assignee_id)
        db.close()


if __name__ == "__main__":
    unittest.main()
