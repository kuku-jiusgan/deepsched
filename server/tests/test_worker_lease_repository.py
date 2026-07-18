import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.repositories.worker_lease_repository import acquire_worker_lease


class WorkerLeaseRepositoryTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)

    def test_only_current_owner_can_renew_active_lease(self):
        first = self.session_factory()
        second = self.session_factory()
        try:
            self.assertTrue(acquire_worker_lease(first, "reminders", "worker-a", 30))
            self.assertFalse(acquire_worker_lease(second, "reminders", "worker-b", 30))
            self.assertTrue(acquire_worker_lease(first, "reminders", "worker-a", 30))
        finally:
            first.close()
            second.close()


if __name__ == "__main__":
    unittest.main()
