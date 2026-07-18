from datetime import datetime, timedelta
import hashlib
import secrets

from app.models import AuthSession, LoginFailure
from app.repositories.auth_repository import (
    add_session,
    delete_login_failure,
    delete_session,
    delete_user_sessions,
    find_login_failure,
    find_session,
    find_user,
    prune_login_failures,
)


def create_session(db, user_id: int, username: str, idle_timeout_seconds: int) -> str:
    token = secrets.token_hex(32)
    now = datetime.now()
    add_session(db, AuthSession(
        token_hash=_token_hash(token),
        user_id=user_id,
        username=username,
        expires_at=now + timedelta(seconds=idle_timeout_seconds),
        last_seen_at=now,
    ))
    return token


def resolve_session_user(db, token: str, idle_timeout_seconds: int, refresh: bool = True):
    session = find_session(db, _token_hash(token))
    now = datetime.now()
    if session is None or session.expires_at < now:
        if session is not None:
            db.delete(session)
        return None
    user = find_user(db, session.user_id)
    if user is None or not user.is_active:
        db.delete(session)
        return None
    if refresh:
        session.last_seen_at = now
        session.expires_at = now + timedelta(seconds=idle_timeout_seconds)
    return user


def session_username(db, token: str) -> str | None:
    session = find_session(db, _token_hash(token))
    if session is None or session.expires_at < datetime.now():
        return None
    return session.username


def revoke_session(db, token: str) -> None:
    delete_session(db, _token_hash(token))


def revoke_user_sessions(db, user_id: int) -> None:
    delete_user_sessions(db, user_id)


def check_throttle(db, key: str) -> bool:
    record = find_login_failure(db, key)
    return bool(record and record.locked_until and record.locked_until > datetime.now())


def record_failure(
    db,
    key: str,
    window_seconds: int,
    lock_seconds: int,
    maximum_failures: int,
    maximum_keys: int,
) -> None:
    now = datetime.now()
    cutoff = now - timedelta(seconds=window_seconds)
    prune_login_failures(db, cutoff, maximum_keys)
    record = find_login_failure(db, key)
    if record is None or record.first_failed_at < cutoff:
        if record is not None:
            db.delete(record)
        db.add(LoginFailure(key=key, failure_count=1, first_failed_at=now))
        return
    record.failure_count += 1
    if record.failure_count >= maximum_failures:
        record.locked_until = now + timedelta(seconds=lock_seconds)


def clear_failure(db, key: str) -> None:
    delete_login_failure(db, key)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
