import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, User
from app.services.project_access_service import (
    ProjectNotVisibleError,
    get_visible_project,
    list_visible_projects,
)


class ProjectAccessServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.owner = User(username="owner", display_name="负责人", role="分析员", is_active=True)
        self.other = User(username="other", display_name="其他人", role="分析员", is_active=True)
        self.project_admin = User(username="pm", display_name="项目管理员", role="项目管理员", is_active=True)
        self.director = User(username="director", display_name="所长", role="分析所所长", is_active=True)
        self.system_admin = User(username="admin2", display_name="系统管理员", role="系统管理员", is_active=True)
        self.db.add_all([self.owner, self.other, self.project_admin, self.director, self.system_admin])
        self.db.flush()
        self.owned_project = Project(name="本人项目", code="P-001", manager_id=self.owner.id)
        self.other_project = Project(name="他人项目", code="P-002", manager_id=self.other.id)
        self.db.add_all([self.owned_project, self.other_project])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_regular_user_only_sees_managed_projects(self):
        projects = list_visible_projects(self.db, self.owner)
        self.assertEqual([self.owned_project.id], [project.id for project in projects])

    def test_regular_user_cannot_open_other_project(self):
        with self.assertRaises(ProjectNotVisibleError):
            get_visible_project(self.db, self.other_project.id, self.owner)

    def test_privileged_roles_see_all_projects(self):
        for user in [self.project_admin, self.director, self.system_admin]:
            with self.subTest(role=user.role):
                projects = list_visible_projects(self.db, user)
                self.assertEqual(2, len(projects))


if __name__ == "__main__":
    unittest.main()