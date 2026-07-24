import time, json
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger
from app.core.database import SessionLocal
from app.services.auth_session_service import session_username
from app.services.audit_log_service import has_business_audit_since, record_audit_log

AUDIT_IGNORED_PATHS = {"/api/v1/users/keep-alive"}
LOGIN_PATHS = {"/api/v1/users/login", "/api/v1/wecom-auth/login"}

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        started_at = datetime.now()
        path = request.scope.get("path", "")
        client_ip = request.client.host if request.client else "unknown"
        operator = "anonymous"
        token = ""
        authorization = request.headers.get("authorization") or ""
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        if token:
            db = SessionLocal()
            try:
                operator = session_username(db, token) or operator
            finally:
                db.close()

        try:
            response = await call_next(request)
            status = response.status_code
            duration_ms = int((time.time() - start) * 1000)
            success = status < 400
            
            if path != "/api/v1/health":
                logger.log(
                    operator=operator,
                    action=f"{request.method} {path}",
                    target=path,
                    success=success,
                    detail=f"HTTP {status} ({duration_ms}ms)",
                    method=request.method,
                    path=path,
                    client_ip=client_ip,
                )
                should_record_audit = (
                    request.method in {"POST", "PUT", "PATCH", "DELETE"}
                    and path not in AUDIT_IGNORED_PATHS
                    and not (success and path in LOGIN_PATHS)
                )
                if should_record_audit:
                    db = SessionLocal()
                    try:
                        if not has_business_audit_since(db, operator, started_at):
                            record_audit_log(
                                db, operator, f"HTTP {request.method}", "api_request", None,
                                {"path": path, "status": status, "success": success, "client_ip": client_ip, "duration_ms": duration_ms},
                            )
                            db.commit()
                    finally:
                        db.close()
            return response
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            if path != "/api/v1/health":
                logger.log(
                    operator=operator,
                    action=f"{request.method} {path}",
                    target=path,
                    success=False,
                    detail=str(e)[:200],
                    method=request.method,
                    path=path,
                    client_ip=client_ip,
                )
            raise
