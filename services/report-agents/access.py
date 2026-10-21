"""Authenticate the chat gateway and bind every report request to its user."""
import hmac
import os
import re
from urllib.parse import unquote

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

USER = re.compile(r"u_[0-9a-f]{64}")
SESSION = re.compile(r"[a-zA-Z0-9_-]{1,128}")


class ReportAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health" and request.method == "GET":
            return await call_next(request)
        expected = os.environ.get("API_KEY", "")
        if not expected:
            return JSONResponse(status_code=503, content={"detail": "Service authentication not configured"})
        if not hmac.compare_digest(request.headers.get("X-API-Key", ""), expected):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        user = request.headers.get("X-Report-User", "")
        if not USER.fullmatch(user):
            return JSONResponse(status_code=401, content={"detail": "Verified user required"})
        parts = [unquote(part) for part in request.url.path.split("/") if part]
        if any(part in {".", ".."} or any(char in part for char in "/\\\x00") for part in parts):
            return JSONResponse(status_code=400, content={"detail": "Invalid path"})
        allowed = False
        if len(parts) in {2, 3} and parts[0] == "reports" and request.method == "GET":
            allowed = parts[1] == user
        elif len(parts) == 6 and parts[:3] == ["apps", "report_agents", "users"] and parts[4] == "sessions":
            allowed = parts[3] == user and bool(SESSION.fullmatch(parts[5])) and request.method in {"GET", "POST", "DELETE"}
        elif parts in [["run"], ["run_sse"]] and request.method == "POST":
            try:
                body = await request.json()
                allowed = (isinstance(body, dict) and body.get("userId") == user
                           and body.get("appName") == "report_agents"
                           and isinstance(body.get("sessionId"), str)
                           and bool(SESSION.fullmatch(body["sessionId"])))
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})
        if not allowed:
            return JSONResponse(status_code=403, content={"detail": "Report ownership or route mismatch"})
        return await call_next(request)
