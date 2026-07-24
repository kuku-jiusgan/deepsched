ROLE_PRIORITY = ["系统管理员", "分析所所长", "技术组长", "项目管理员", "技术员"]


def normalized_roles(roles: list[str] | None, fallback_role: str) -> list[str]:
    values = roles if isinstance(roles, list) else []
    unique = [role for role in ROLE_PRIORITY if role in values]
    return unique or [fallback_role]


def user_roles(user) -> list[str]:
    return normalized_roles(user.roles, user.role)


def has_role(user, role: str) -> bool:
    return role in user_roles(user)


def has_any_role(user, roles: set[str]) -> bool:
    return bool(set(user_roles(user)) & roles)


def primary_role(roles: list[str]) -> str:
    return normalized_roles(roles, "技术员")[0]
