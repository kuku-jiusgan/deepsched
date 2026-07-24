from datetime import datetime, timedelta

from app.models import AuditLog, User


HIDDEN_TECHNICAL_PATHS = {"/api/v1/users/keep-alive"}
USER_AUDIT_FIELDS = {
    "username": "登录账号",
    "display_name": "姓名",
    "roles": "角色",
    "email": "邮箱",
    "phone": "手机号",
    "wecom_id": "企业微信号",
    "is_active": "账号状态",
}
PROJECT_AUDIT_FIELDS = {
    "code": "项目编号",
    "name": "项目名称",
    "client_name": "客户名称",
    "estimated_hours": "预计总工时",
    "priority": "优先级",
    "manager_name": "项目负责人",
    "start_date": "项目开始时间",
    "end_date": "项目结束时间",
}


def record_audit_log(db, user_name: str, action: str, target_type: str, target_id: int | None, detail: dict) -> None:
    db.add(AuditLog(
        user_name=user_name,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    ))


def user_audit_snapshot(user) -> dict:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "roles": list(user.roles or [user.role]),
        "email": user.email,
        "phone": user.phone,
        "wecom_id": user.wecom_id,
        "is_active": user.is_active,
    }


def user_audit_detail(user, before: dict | None = None) -> dict:
    current = user_audit_snapshot(user)
    detail = {
        "target_display": f"{current['display_name']}（{current['username']}）",
        **current,
    }
    if before is not None:
        detail["changes"] = [
            {
                "field": USER_AUDIT_FIELDS[key],
                "before": before.get(key),
                "after": value,
            }
            for key, value in current.items()
            if before.get(key) != value
        ]
    return detail


def project_audit_snapshot(project) -> dict:
    return {
        "code": project.code,
        "name": project.name,
        "client_name": project.client_name,
        "estimated_hours": project.estimated_hours,
        "priority": project.priority,
        "manager_name": project.manager.display_name if project.manager else None,
        "start_date": _format_audit_datetime(project.start_date),
        "end_date": _format_audit_datetime(project.end_date),
    }


def project_audit_detail(project, before: dict | None = None) -> dict:
    current = project_audit_snapshot(project)
    detail = {
        "target_display": f"{current['code']} · {current['name']}",
        "project_fields": current,
    }
    if before is not None:
        detail["changes"] = [
            {
                "field": PROJECT_AUDIT_FIELDS[key],
                "before": before.get(key),
                "after": value,
            }
            for key, value in current.items()
            if before.get(key) != value
        ]
    return detail


def _format_audit_datetime(value) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M") if value else None


def has_business_audit_since(db, operator: str, started_at: datetime) -> bool:
    aliases = _operator_aliases(db, operator)
    return db.query(AuditLog).filter(
        AuditLog.target_type != "api_request",
        AuditLog.user_name.in_(aliases),
        AuditLog.created_at >= started_at - timedelta(seconds=1),
    ).first() is not None


def list_audit_logs(db, keyword: str | None = None, action: str | None = None, user_name: str | None = None, start_at=None, end_at=None):
    query = db.query(AuditLog)
    if keyword:
        query = query.filter(AuditLog.action.contains(keyword) | AuditLog.user_name.contains(keyword))
    if action:
        query = query.filter(AuditLog.action == action)
    if user_name:
        query = query.filter(AuditLog.user_name == user_name)
    if start_at:
        query = query.filter(AuditLog.created_at >= start_at)
    if end_at:
        query = query.filter(AuditLog.created_at <= end_at)
    logs = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).all()
    visible_logs = [
        log for log in logs
        if not isinstance(log.detail, dict)
        or log.detail.get("path") not in HIDDEN_TECHNICAL_PATHS
    ]
    return [log for log in visible_logs if not _is_duplicate_api_log(db, log, visible_logs)]


def _is_duplicate_api_log(db, log: AuditLog, logs: list[AuditLog]) -> bool:
    if log.target_type != "api_request":
        return False
    aliases = _operator_aliases(db, log.user_name)
    request_target_id = _path_target_id((log.detail or {}).get("path", ""))
    return any(
        candidate.target_type != "api_request"
        and candidate.user_name in aliases
        and abs((candidate.created_at - log.created_at).total_seconds()) <= 2
        and (request_target_id is None or candidate.target_id in {None, request_target_id})
        for candidate in logs
    )


def _operator_aliases(db, operator: str) -> set[str]:
    user = db.query(User).filter(
        (User.username == operator) | (User.display_name == operator)
    ).first()
    return {operator, user.username, user.display_name} if user else {operator}


def _path_target_id(path: str) -> int | None:
    numeric_parts = [int(part) for part in path.split("/") if part.isdigit()]
    return numeric_parts[-1] if numeric_parts else None
