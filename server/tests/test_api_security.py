import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import protected_router
from app.api.alert_rules import _push_config_response
from app.api.users import _seed_admin, auth_token, require_authenticated_user
from app.core.database import Base
from app.models import User


class ApiSecurityTest(unittest.TestCase):
    def test_every_business_route_has_authentication_dependency(self):
        routes = [route for route in protected_router.routes if isinstance(route, APIRoute)]
        self.assertGreater(len(routes), 60)

        for route in routes:
            with self.subTest(path=route.path, methods=route.methods):
                dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
                self.assertIn(require_authenticated_user, dependency_calls)

    def test_missing_authorization_header_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            auth_token(None)
        self.assertEqual(401, context.exception.status_code)

    def test_push_config_response_never_contains_secret(self):
        config = SimpleNamespace(
            id=1,
            wecom_enabled=True,
            wecom_corp_id="corp",
            wecom_agent_id="agent",
            wecom_secret="do-not-return",
        )

        payload = _push_config_response(config).model_dump()

        self.assertNotIn("wecom_secret", payload)
        self.assertTrue(payload["has_wecom_secret"])

    def test_admin_is_not_seeded_without_explicit_password(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            with patch.dict(os.environ, {}, clear=True):
                _seed_admin(db)
            self.assertIsNone(db.query(User).filter(User.username == "admin").first())
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
