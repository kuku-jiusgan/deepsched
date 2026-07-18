from datetime import datetime

from app.models import AuthSession, LoginFailure, User


def add_session(db, session: AuthSession) -> None:
    db.add(session)


def find_session(db, token_hash: str) -> AuthSession | None:
    return db.query(AuthSession).filter(AuthSession.token_hash == token_hash).first()


def delete_session(db, token_hash: str) -> None:
    db.query(AuthSession).filter(AuthSession.token_hash == token_hash).delete()


def delete_user_sessions(db, user_id: int) -> None:
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()


def find_user(db, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def find_login_failure(db, key: str) -> LoginFailure | None:
    return db.query(LoginFailure).filter(LoginFailure.key == key).first()


def delete_login_failure(db, key: str) -> None:
    db.query(LoginFailure).filter(LoginFailure.key == key).delete()


def prune_login_failures(db, cutoff: datetime, maximum: int) -> None:
    db.query(LoginFailure).filter(
        LoginFailure.first_failed_at < cutoff,
        (LoginFailure.locked_until.is_(None)) | (LoginFailure.locked_until < datetime.now()),
    ).delete(synchronize_session=False)
    excess = db.query(LoginFailure).count() - maximum
    if excess <= 0:
        return
    stale_keys = [
        row[0]
        for row in db.query(LoginFailure.key)
        .order_by(LoginFailure.first_failed_at)
        .limit(excess)
        .all()
    ]
    if stale_keys:
        db.query(LoginFailure).filter(LoginFailure.key.in_(stale_keys)).delete(synchronize_session=False)
