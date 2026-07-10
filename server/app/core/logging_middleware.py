import time, json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        operator = "anonymous"
        token = ""
        authorization = request.headers.get("authorization") or ""
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        # Import here to avoid circular imports
        from app.api.users import TOKENS
        if token and token in TOKENS:
            entry = TOKENS.get(token)
            if entry:
                operator = entry.get('username', f"user_{entry.get('user_id', 'unknown')}")

        try:
            response = await call_next(request)
            status = response.status_code
            duration_ms = int((time.time() - start) * 1000)
            success = status < 400
            
            if request.url.path != "/api/v1/health":
                logger.log(
                    operator=operator,
                    action=f"{request.method} {request.url.path}",
                    target=request.url.path,
                    success=success,
                    detail=f"HTTP {status} ({duration_ms}ms)",
                    method=request.method,
                    path=request.url.path,
                )
            return response
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            if request.url.path != "/api/v1/health":
                logger.log(
                    operator=operator,
                    action=f"{request.method} {request.url.path}",
                    target=request.url.path,
                    success=False,
                    detail=str(e)[:200],
                    method=request.method,
                    path=request.url.path,
                )
            raise
