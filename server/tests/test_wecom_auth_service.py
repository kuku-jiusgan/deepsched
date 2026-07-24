import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import AuthSession, PushChannelConfig, User
from app.services.wecom_auth_service import (
    WeComAccountBindingError,
    WeComAuthenticationError,
    build_authorize_url,
    login_with_wecom,
)


class WeComAuthServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.config = PushChannelConfig(
            wecom_enabled=True,
            wecom_corp_id="corp-id",
            wecom_agent_id="1000002",
            wecom_secret="application-secret",
        )
        self.db.add(self.config)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _state(self) -> str:
        url = build_authorize_url(self.db, "https://example.com/login", 300)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(["corp-id"], query["appid"])
        self.assertEqual(["https://example.com/login"], query["redirect_uri"])
        return query["state"][0]

    @patch("app.services.wecom_auth_service._get_json")
    def test_bound_active_member_gets_system_session(self, get_json):
        user = User(
            username="zhangsan", display_name="张三", role="技术员",
            roles=["技术员"], wecom_id="zhangsan-wecom", is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        get_json.side_effect = [
            {"errcode": 0, "access_token": "access-token"},
            {"errcode": 0, "UserId": "zhangsan-wecom"},
        ]

        result = login_with_wecom(self.db, "oauth-code", self._state(), 300, 10800)

        self.assertEqual("zhangsan", result["user"]["username"])
        self.assertTrue(result["token"])
        self.assertEqual(1, self.db.query(AuthSession).count())

    def test_tampered_state_is_rejected(self):
        state = self._state()
        with self.assertRaises(WeComAuthenticationError):
            login_with_wecom(self.db, "oauth-code", f"{state}x", 300, 10800)

    @patch("app.services.wecom_auth_service._get_json")
    def test_state_cannot_be_reused(self, get_json):
        user = User(
            username="lisi", display_name="李四", role="技术员",
            roles=["技术员"], wecom_id="lisi-wecom", is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        get_json.side_effect = [
            {"errcode": 0, "access_token": "access-token"},
            {"errcode": 0, "UserId": "lisi-wecom"},
        ]
        state = self._state()

        login_with_wecom(self.db, "oauth-code", state, 300, 10800)

        with self.assertRaisesRegex(WeComAuthenticationError, "已使用"):
            login_with_wecom(self.db, "another-code", state, 300, 10800)

    @patch("app.services.wecom_auth_service._get_json")
    def test_unbound_member_is_rejected(self, get_json):
        get_json.side_effect = [
            {"errcode": 0, "access_token": "access-token"},
            {"errcode": 0, "UserId": "unbound-user"},
        ]
        with self.assertRaisesRegex(WeComAccountBindingError, "尚未绑定"):
            login_with_wecom(self.db, "oauth-code", self._state(), 300, 10800)

    @patch("app.services.wecom_auth_service._get_json")
    def test_duplicate_bindings_are_rejected(self, get_json):
        self.db.add_all([
            User(username="first", display_name="甲", role="技术员", wecom_id="duplicate", is_active=True),
            User(username="second", display_name="乙", role="技术员", wecom_id="duplicate", is_active=True),
        ])
        self.db.commit()
        get_json.side_effect = [
            {"errcode": 0, "access_token": "access-token"},
            {"errcode": 0, "UserId": "duplicate"},
        ]
        with self.assertRaisesRegex(WeComAccountBindingError, "多个系统用户"):
            login_with_wecom(self.db, "oauth-code", self._state(), 300, 10800)


if __name__ == "__main__":
    unittest.main()
