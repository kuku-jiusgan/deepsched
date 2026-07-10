from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.core.config import get_settings
from app.core.schema_migrations import ensure_runtime_schema
from app.models import models
from app.api import users, schedule_rules, instruments, projects, schedules, stats, notifications, task_types, alert_rules, calendar_api, project_plan_schedules

Base.metadata.create_all(bind=engine)
ensure_runtime_schema(engine)

app = FastAPI(title="资源智能调度平台", version="1.0.0")
settings = get_settings()
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_json_utf8_charset(request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type == "application/json":
        response.headers["content-type"] = "application/json; charset=utf-8"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

from app.core.logging_middleware import LoggingMiddleware
app.add_middleware(LoggingMiddleware)

app.include_router(instruments.router)
app.include_router(projects.router)
app.include_router(schedules.router)
app.include_router(project_plan_schedules.router)
app.include_router(schedule_rules.router)
app.include_router(users.router)
app.include_router(stats.router)
app.include_router(notifications.router)
app.include_router(task_types.router)
app.include_router(alert_rules.router)
app.include_router(calendar_api.router)

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

import os, glob
from fastapi import Depends, Query
from app.core.database import get_db
@app.get("/api/v1/logs")
def get_logs(
    hours: int = Query(6, ge=1, le=24, description="最近多少小时的日志"),
    token: str = Depends(users.auth_token),
    db = Depends(get_db),
):
    users.require_admin(token, db)
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    files = sorted(glob.glob(os.path.join(log_dir, "operations_*.log")), reverse=True)
    entries = []
    cutoff = __import__('time').time() - hours * 3600
    for f in files[:4]:  # Check up to 4 recent files
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        entry = __import__('json').loads(line.strip())
                        ts = __import__('datetime').datetime.fromisoformat(entry["timestamp"])
                        if ts.timestamp() >= cutoff:
                            entries.append(entry)
                    except:
                        pass
        except:
            pass
    return {"count": len(entries), "entries": entries[-500:]}  # Return last 500
