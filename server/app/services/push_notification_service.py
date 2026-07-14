from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from app.models import AlertRule, Notification, PushChannelConfig, User


class PushConfigError(Exception):
    pass


CONFIRM_REQUIRED_TYPES = {"instrument_fault_schedule_conflict"}


@dataclass
class WeComSendResult:
    success: bool
    error_message: str | None = None


_TOKEN_CACHE: dict[str, object] = {"token": None, "expires_at": 0.0}


def get_push_config(db) -> PushChannelConfig:
    config = db.query(PushChannelConfig).order_by(PushChannelConfig.id).first()
    if config:
        return config
    config = PushChannelConfig(wecom_enabled=False)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_push_config(db, data: dict) -> PushChannelConfig:
    config = get_push_config(db)
    for field, value in data.items():
        setattr(config, field, value)
    db.commit()
    db.refresh(config)
    _TOKEN_CACHE["token"] = None
    _TOKEN_CACHE["expires_at"] = 0.0
    return config


def push_by_rule(
    db,
    rule_type: str,
    users: Iterable[User],
    title: str,
    content: str,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
    context_roles: Iterable[str] | None = None,
) -> int:
    rule = db.query(AlertRule).filter(AlertRule.rule_type == rule_type).first()
    if rule and not rule.enabled:
        return 0

    enable_site = True if not rule else bool(rule.enable_site)
    enable_wecom = False if not rule else bool(rule.enable_wecom)
    unique_users = _notification_recipients(rule, users, context_roles)
    sent_count = 0

    if enable_site:
        for user in unique_users:
            db.add(_notification(
                user=user,
                rule_type=rule_type,
                title=title,
                content=content,
                channel="site",
                delivery_status="success",
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            ))
            sent_count += 1

    if enable_wecom:
        sent_count += _push_wecom(
            db,
            unique_users,
            rule_type,
            title,
            content,
            related_entity_type,
            related_entity_id,
        )

    return sent_count


def _push_wecom(
    db,
    users: list[User],
    rule_type: str,
    title: str,
    content: str,
    related_entity_type: str | None,
    related_entity_id: int | None,
) -> int:
    config = get_push_config(db)
    if not config.wecom_enabled:
        return 0

    wecom_users = [user for user in users if user.wecom_id]
    if not wecom_users:
        for user in users:
            db.add(_notification(
                user=user,
                rule_type=rule_type,
                title=title,
                content=content,
                channel="wecom",
                delivery_status="failed",
                error_message="用户未配置企业微信号",
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            ))
        return 0

    result = _send_wecom_text(config, wecom_users, f"{title}\n{content}")
    for user in wecom_users:
        db.add(_notification(
            user=user,
            rule_type=rule_type,
            title=title,
            content=content,
            channel="wecom",
            delivery_status="success" if result.success else "failed",
            error_message=result.error_message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        ))
    return len(wecom_users) if result.success else 0


def _send_wecom_text(config: PushChannelConfig, users: list[User], content: str) -> WeComSendResult:
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


def _notification_recipients(
    rule: AlertRule | None,
    users: Iterable[User],
    context_roles: Iterable[str] | None,
) -> list[User]:
    active_users = _unique_active_users(users)
    if not rule or rule.notify_roles is None:
        return active_users
    notify_roles = _parse_notify_roles(rule.notify_roles)
    matched_context_roles = notify_roles & set(context_roles or [])
    return [
        user for user in active_users
        if user.role in notify_roles or matched_context_roles
    ]


def _parse_notify_roles(value: str) -> set[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return set()
    if not isinstance(parsed, list):
        return set()
    return {role for role in parsed if isinstance(role, str) and role}


def _unique_active_users(users: Iterable[User]) -> list[User]:
    result: list[User] = []
    seen = set()
    for user in users:
        if not user or not user.username or not user.is_active or user.username in seen:
            continue
        seen.add(user.username)
        result.append(user)
    return result


def _notification(
    user: User,
    rule_type: str,
    title: str,
    content: str,
    channel: str,
    delivery_status: str,
    related_entity_type: str | None,
    related_entity_id: int | None,
    error_message: str | None = None,
) -> Notification:
    return Notification(
        user_name=user.username,
        n_type=rule_type,
        channel=channel,
        delivery_status=delivery_status,
        error_message=error_message,
        title=title,
        content=content,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        is_confirmed=False if rule_type in CONFIRM_REQUIRED_TYPES else None,
    )
