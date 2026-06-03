import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database.session import AsyncSessionLocal
from app.repositories.system_settings_repository import SystemSettingsRepository

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 10.0

# Always reachable regardless of maintenance_mode.
_EXACT_WHITELIST = {"/health", "/auth/login", "/docs", "/openapi.json"}
_PREFIX_WHITELIST = ("/admin/settings",)

_cache: dict = {"value": False, "expires_at": 0.0}


def _is_whitelisted(path: str) -> bool:
    if path in _EXACT_WHITELIST:
        return True
    return any(path.startswith(prefix) for prefix in _PREFIX_WHITELIST)


async def _maintenance_enabled() -> bool:
    now = time.monotonic()
    if now < _cache["expires_at"]:
        return _cache["value"]

    value = False
    try:
        async with AsyncSessionLocal() as session:
            raw = await SystemSettingsRepository().get_one(session, "maintenance_mode")
        value = (raw or "").lower() == "true"
    except Exception:
        # Fail open: a transient DB error must not lock the platform for everyone.
        logger.warning("maintenance_mode lookup failed; passing through", exc_info=True)
        value = False

    _cache["value"] = value
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return value


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_whitelisted(request.url.path):
            return await call_next(request)

        if await _maintenance_enabled():
            return JSONResponse(
                {"detail": "Service is under maintenance"},
                status_code=503,
            )

        return await call_next(request)
