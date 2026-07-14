import hashlib
import hmac
import json as _json
import os
import re
import secrets
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.services.user_directory_service import list_user_directory
from app.schemas.schemas import UserCreate, UserDirectoryOut, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])

ROLE_OPTIONS = ["系统管理员", "项目管理员", "分析所所长", "分析员"]
ADMIN_ROLE = "系统管理员"
IDLE_TIMEOUT_SECONDS = 30 * 60
LOGIN_FAILURE_WINDOW_SECONDS = 10 * 60
LOGIN_LOCK_SECONDS = 15 * 60
MAX_LOGIN_FAILURES = 5
MAX_LOGIN_FAILURE_KEYS = 5000
PBKDF2_ITERATIONS = 120_000
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")

_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tokens.json")


def _load_tokens() -> Dict[str, Dict]:
    try:
        with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
            tokens = _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError):
        return {}
    now = time.time()
    sanitized = {}
    for token, entry in tokens.items():
        expires_at = float(entry.get("expires_at", 0))
        if now < expires_at <= now + IDLE_TIMEOUT_SECONDS:
            sanitized[token] = entry
    return sanitized


def _save_tokens(tokens: Dict[str, Dict]):
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
        _json.dump(tokens, f)


TOKENS: Dict[str, Dict] = _load_tokens()
LOGIN_FAILURES: Dict[str, Dict[str, float | int]] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-constant-login-cost")


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = stored.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
            return hmac.compare_digest(candidate, digest)
        except (TypeError, ValueError):
            return False
    if ":" in stored:
        salt, digest = stored.split(":", 1)
        candidate = hashlib.sha256((salt + password).encode()).hexdigest()
        return hmac.compare_digest(candidate, digest)
    return False


def needs_password_rehash(stored: str) -> bool:
    return not stored.startswith("pbkdf2_sha256$")


def create_token(user_id: int, username: str = "") -> str:
    token = secrets.token_hex(32)
    now = time.time()
    TOKENS[token] = {
        "user_id": user_id,
        "username": username,
        "expires_at": now + IDLE_TIMEOUT_SECONDS,
        "last_seen_at": now,
    }
    _save_tokens(TOKENS)
    return token


def auth_token(
    authorization: str | None = Header(None),
) -> str:
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value
    raise HTTPException(status_code=401, detail="未登录或登录已过期")


def get_current_user(token: str, db: Session) -> User:
    entry = TOKENS.get(token)
    now = time.time()
    if not entry or float(entry.get("expires_at", 0)) < now:
        if entry:
            TOKENS.pop(token, None)
            _save_tokens(TOKENS)
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    user = db.query(User).filter(User.id == entry["user_id"]).first()
    if not user or not user.is_active:
        TOKENS.pop(token, None)
        _save_tokens(TOKENS)
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    entry["last_seen_at"] = now
    entry["expires_at"] = now + IDLE_TIMEOUT_SECONDS
    _save_tokens(TOKENS)
    return user


def require_admin(token: str, db: Session) -> User:
    user = get_current_user(token, db)
    if user.role != ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="仅系统管理员可管理用户")
    return user


def validate_username(username: str) -> str:
    value = username.strip()
    if not USERNAME_PATTERN.match(value):
        raise HTTPException(status_code=400, detail="用户名需为3-50位英文、数字、点、下划线或短横线")
    return value


def validate_password_strength(password: str | None) -> None:
    if not password:
        return
    has_letter = any(ch.isalpha() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    if len(password) < 8 or not has_letter or not has_digit:
        raise HTTPException(status_code=400, detail="密码至少8位，且必须包含字母和数字")


def active_admin_count(db: Session, exclude_user_id: int | None = None) -> int:
    query = db.query(User).filter(User.role == ADMIN_ROLE, User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


def ensure_admin_safety(db: Session, operator: User, target: User, data: UserCreate | None = None, deleting: bool = False) -> None:
    if operator.id == target.id and deleting:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if data and operator.id == target.id and not data.is_active:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    if data and operator.id == target.id and data.role != ADMIN_ROLE:
        raise HTTPException(status_code=400, detail="不能修改当前登录账号的管理员角色")
    if target.role != ADMIN_ROLE:
        return
    will_remove_admin = deleting or (data is not None and (data.role != ADMIN_ROLE or not data.is_active))
    if will_remove_admin and active_admin_count(db, target.id) <= 0:
        raise HTTPException(status_code=400, detail="至少需要保留一个启用的系统管理员")


def login_key(request: Request, username: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{username.lower()}"


def check_login_throttle(request: Request, username: str) -> None:
    prune_login_failures()
    record = LOGIN_FAILURES.get(login_key(request, username))
    now = time.time()
    if record and float(record.get("locked_until", 0)) > now:
        raise HTTPException(status_code=429, detail="登录失败次数过多，请15分钟后再试")


def record_login_failure(request: Request, username: str) -> None:
    prune_login_failures()
    key = login_key(request, username)
    now = time.time()
    record = LOGIN_FAILURES.get(key)
    if not record or now - float(record.get("first_failed_at", 0)) > LOGIN_FAILURE_WINDOW_SECONDS:
        LOGIN_FAILURES[key] = {"count": 1, "first_failed_at": now, "locked_until": 0}
        return
    count = int(record.get("count", 0)) + 1
    record["count"] = count
    if count >= MAX_LOGIN_FAILURES:
        record["locked_until"] = now + LOGIN_LOCK_SECONDS


def clear_login_failure(request: Request, username: str) -> None:
    LOGIN_FAILURES.pop(login_key(request, username), None)


def prune_login_failures() -> None:
    now = time.time()
    expired_keys = [
        key for key, record in LOGIN_FAILURES.items()
        if float(record.get("locked_until", 0)) < now
        and now - float(record.get("first_failed_at", 0)) > LOGIN_FAILURE_WINDOW_SECONDS
    ]
    for key in expired_keys:
        LOGIN_FAILURES.pop(key, None)
    if len(LOGIN_FAILURES) <= MAX_LOGIN_FAILURE_KEYS:
        return
    sorted_items = sorted(LOGIN_FAILURES.items(), key=lambda item: float(item[1].get("first_failed_at", 0)))
    for key, _ in sorted_items[: len(LOGIN_FAILURES) - MAX_LOGIN_FAILURE_KEYS]:
        LOGIN_FAILURES.pop(key, None)


def _seed_admin(db: Session):
    if db.query(User).filter(User.username == "admin").first():
        return
    db.add(
        User(
            username="admin",
            display_name="系统管理员",
            role=ADMIN_ROLE,
            password_hash=hash_password("Admin@123456"),
            is_active=True,
        )
    )
    db.commit()


@router.get("/directory", response_model=List[UserDirectoryOut])
def get_user_directory(
    token: str = Depends(auth_token),
    db: Session = Depends(get_db),
):
    get_current_user(token, db)
    return list_user_directory(db)


@router.get("", response_model=List[UserOut])
def list_users(token: str = Depends(auth_token), db: Session = Depends(get_db)):
    _seed_admin(db)
    require_admin(token, db)
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut)
def create_user(data: UserCreate, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    require_admin(token, db)
    username = validate_username(data.username)
    validate_password_strength(data.password)
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail=f"用户名 {username} 已存在")
    if data.role not in ROLE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效角色：{data.role}")
    if not data.password:
        raise HTTPException(status_code=400, detail="请设置登录密码")
    payload = data.model_dump()
    payload["username"] = username
    password = payload.pop("password")
    user = User(**payload, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserCreate, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    operator = require_admin(token, db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    username = validate_username(data.username)
    validate_password_strength(data.password)
    existing = db.query(User).filter(User.username == username, User.id != user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"用户名 {username} 已被其他用户使用")
    if data.role not in ROLE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效角色：{data.role}")
    ensure_admin_safety(db, operator, user, data)
    payload = data.model_dump()
    payload["username"] = username
    password = payload.pop("password", None)
    for key, val in payload.items():
        setattr(user, key, val)
    if password:
        user.password_hash = hash_password(password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    operator = require_admin(token, db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    ensure_admin_safety(db, operator, user, deleting=True)
    db.delete(user)
    db.commit()
    return {"detail": "已删除"}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class ChangeMyPasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


@router.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _seed_admin(db)
    username = data.username.strip()
    check_login_throttle(request, username)
    user = db.query(User).filter(User.username == username).first()
    stored_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_ok = verify_password(data.password, stored_hash or DUMMY_PASSWORD_HASH)
    if not user or not password_ok:
        record_login_failure(request, username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        record_login_failure(request, username)
        raise HTTPException(status_code=403, detail="账号已停用")
    if needs_password_rehash(user.password_hash or ""):
        user.password_hash = hash_password(data.password)
        db.commit()
    clear_login_failure(request, username)
    token = create_token(user.id, user.username)
    return {
        "token": token,
        "expires_in": IDLE_TIMEOUT_SECONDS,
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role},
    }


@router.get("/me")
def get_me(token: str = Depends(auth_token), db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}


@router.post("/me/password")
def change_my_password(data: ChangeMyPasswordRequest, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    if not verify_password(data.old_password, user.password_hash or ""):
        raise HTTPException(status_code=400, detail="原密码不正确")
    validate_password_strength(data.new_password)
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    TOKENS.pop(token, None)
    _save_tokens(TOKENS)
    return {"detail": "密码已修改，请重新登录"}


@router.post("/keep-alive")
def keep_alive(token: str = Depends(auth_token), db: Session = Depends(get_db)):
    get_current_user(token, db)
    return {"detail": "会话已续期", "expires_in": IDLE_TIMEOUT_SECONDS}


@router.post("/logout")
def logout(token: str = Depends(auth_token)):
    TOKENS.pop(token, None)
    _save_tokens(TOKENS)
    return {"detail": "已退出"}
