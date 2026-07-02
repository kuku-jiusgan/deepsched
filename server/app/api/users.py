import hashlib, os, secrets, time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from pydantic import BaseModel
from app.core.database import get_db
from app.models import User
from app.schemas.schemas import UserCreate, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])

ROLE_OPTIONS = ["系统管理员", "项目管理员", "项目负责人", "分析员"]

# Token persistence file
import json as _json
_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "tokens.json")

def _load_tokens() -> Dict[str, Dict]:
    try:
        with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError):
        return {}

def _save_tokens(tokens: Dict[str, Dict]):
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
        _json.dump(tokens, f)

TOKENS: Dict[str, Dict] = _load_tokens()

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_password(password: str, stored: str) -> bool:
    if not stored or ":" not in stored:
        return False
    salt, h = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h

def create_token(user_id: int, username: str = "") -> str:
    token = secrets.token_hex(32)
    TOKENS[token] = {"user_id": user_id, "username": username, "expires_at": time.time() + 86400}
    _save_tokens(TOKENS)
    return token

def get_current_user(token: str, db: Session) -> User:
    entry = TOKENS.get(token)
    if not entry or entry["expires_at"] < time.time():
        if entry:
            TOKENS.pop(token, None)
            _save_tokens(TOKENS)
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    user = db.query(User).filter(User.id == entry["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user

def _seed_admin(db: Session):
    if db.query(User).filter(User.username == "admin").first():
        return
    db.add(User(username="admin", display_name="系统管理员", role="系统管理员",
                password_hash=hash_password("admin123"), is_active=True))
    db.commit()

# ---- CRUD ----
@router.get("", response_model=List[UserOut])
def list_users(token: str, db: Session = Depends(get_db)):
    get_current_user(token, db)
    _seed_admin(db)
    return db.query(User).order_by(User.id).all()

@router.post("", response_model=UserOut)
def create_user(data: UserCreate, token: str, db: Session = Depends(get_db)):
    get_current_user(token, db)
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=409, detail=f"用户名 {data.username} 已存在")
    if data.role not in ROLE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效角色：{data.role}")
    d = data.model_dump()
    pw = d.pop("password", None)
    user = User(**d, password_hash=hash_password(pw) if pw else None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserCreate, token: str, db: Session = Depends(get_db)):
    get_current_user(token, db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = db.query(User).filter(User.username == data.username, User.id != user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"用户名 {data.username} 已被其他用户使用")
    if data.role not in ROLE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效角色：{data.role}")
    d = data.model_dump()
    pw = d.pop("password", None)
    for key, val in d.items():
        setattr(user, key, val)
    if pw:
        user.password_hash = hash_password(pw)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(user_id: int, token: str, db: Session = Depends(get_db)):
    get_current_user(token, db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"detail": "已删除"}

# ---- Auth ----
class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    _seed_admin(db)
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash or ""):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    token = create_token(user.id, user.username)
    return {"token": token, "user": {"id": user.id, "username": user.username,
            "display_name": user.display_name, "role": user.role}}

@router.get("/me")
def get_me(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    return {"id": user.id, "username": user.username,
            "display_name": user.display_name, "role": user.role}

@router.post("/logout")
def logout(token: str):
    TOKENS.pop(token, None)
    _save_tokens(TOKENS)
    return {"detail": "已退出"}

