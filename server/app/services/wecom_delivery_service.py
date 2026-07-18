from __future__ import annotations

import threading
import time
import logging
import uuid
import urllib.error
import urllib.parse
import urllib.request
import json
from dataclasses import dataclass

from app.core.database import SessionLocal
from app.models import Notification, PushChannelConfig, User
from app.repositories.worker_lease_repository import acquire_worker_lease


PENDING_DELIVERY_POLL_SECONDS = 1
PENDING_DELIVERY_BATCH_SIZE = 50
WECOM_LEASE_SECONDS = 5
WECOM_LEASE_NAME = "wecom-delivery"


class PushConfigError(Exception):
    pass


@dataclass
class WeComSendResult:
    success: bool
    error_message: str | None = None


_TOKEN_CACHE: dict[str, object] = {"token": None, "expires_at": 0.0}
_wake_event = threading.Event()
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_owner_id = uuid.uuid4().hex
_logger = logging.getLogger(__name__)


def start_wecom_delivery_worker() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_delivery_loop,
        name="wecom-delivery-worker",
        daemon=True,
    )
    _worker_thread.start()
    _wake_event.set()


def stop_wecom_delivery_worker() -> None:
    _stop_event.set()
    _wake_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=2)


def enqueue_wecom_delivery() -> None:
    _wake_event.set()


def reset_wecom_token_cache() -> None:
    _TOKEN_CACHE["token"] = None
    _TOKEN_CACHE["expires_at"] = 0.0


def _delivery_loop() -> None:
    while not _stop_event.is_set():
        _wake_event.wait(PENDING_DELIVERY_POLL_SECONDS)
        _wake_event.clear()
        db = SessionLocal()
        try:
            if acquire_worker_lease(
                db,
                WECOM_LEASE_NAME,
                _worker_owner_id,
                WECOM_LEASE_SECONDS,
            ):
                _process_pending_wecom_notifications(db)
        except Exception:
            db.rollback()
            _logger.exception("企业微信后台投递失败")
        finally:
            db.close()


def _process_pending_wecom_notifications(db) -> int:
    notifications = (
        db.query(Notification)
        .filter(
            Notification.channel == "wecom",
            Notification.delivery_status == "pending",
        )
        .order_by(Notification.id)
        .limit(PENDING_DELIVERY_BATCH_SIZE)
        .all()
    )
    if not notifications:
        return 0

    config = db.query(PushChannelConfig).order_by(PushChannelConfig.id).first()
    if not config:
        config = PushChannelConfig(wecom_enabled=True)

    for notification in notifications:
        user = db.query(User).filter(User.username == notification.user_name).first()
        if not user or not user.wecom_id:
            notification.delivery_status = "failed"
            notification.error_message = "用户未配置企业微信号"
            continue
        try:
            result = _send_wecom_text(
                config,
                [user],
                f"{notification.title or ''}\n{notification.content or ''}",
            )
        except Exception as exc:
            result = WeComSendResult(False, str(exc))
        notification.delivery_status = "success" if result.success else "failed"
        notification.error_message = result.error_message

    db.commit()
    return len(notifications)


def _send_wecom_text(
    config: PushChannelConfig,
    users: list[User],
    content: str,
) -> WeComSendResult:
    try:
        token = _get_wecom_token(config)
        payload = {
            "touser": "|".join(user.wecom_id for user in users if user.wecom_id),
            "msgtype": "text",
            "agentid": int(config.wecom_agent_id or "0"),
            "text": {"content": content},
            "safe": 0,
        }
        response = _post_json(
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={urllib.parse.quote(token)}",
            payload,
        )
    except (PushConfigError, ValueError, urllib.error.URLError, TimeoutError) as exc:
        return WeComSendResult(False, str(exc))

    if response.get("errcode") != 0:
        return WeComSendResult(False, str(response.get("errmsg") or response))
    return WeComSendResult(True)


def _get_wecom_token(config: PushChannelConfig) -> str:
    if not config.wecom_corp_id or not config.wecom_secret or not config.wecom_agent_id:
        raise PushConfigError("企业微信 CorpID、Secret、AgentId 未配置完整")

    now = time.time()
    cached_token = _TOKEN_CACHE.get("token")
    cached_expires_at = float(_TOKEN_CACHE.get("expires_at") or 0)
    if cached_token and cached_expires_at > now + 60:
        return str(cached_token)

    params = urllib.parse.urlencode({
        "corpid": config.wecom_corp_id,
        "corpsecret": config.wecom_secret,
    })
    response = _get_json(f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?{params}")
    if response.get("errcode") != 0:
        raise PushConfigError(str(response.get("errmsg") or response))

    token = response.get("access_token")
    if not token:
        raise PushConfigError("企业微信未返回 access_token")
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + int(response.get("expires_in") or 7200)
    return str(token)


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))
