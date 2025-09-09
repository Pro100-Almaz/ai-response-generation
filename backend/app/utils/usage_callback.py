import json
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
import structlog

logger = structlog.get_logger()

async def send_usage(payload: Dict[str, Any]):
    """
    Optionally POST usage to your Django monolith (deduct points, etc).
    Configure AI_GW_USAGE_CALLBACK_URL and AI_GW_USAGE_CALLBACK_AUTH.
    Non-blocking; failures are logged and ignored.
    """
    if not settings.USAGE_CALLBACK_URL:
        return
    headers = {"Content-Type": "application/json"}
    if settings.USAGE_CALLBACK_AUTH:
        headers["Authorization"] = settings.USAGE_CALLBACK_AUTH
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(settings.USAGE_CALLBACK_URL, json=payload, headers=headers)
    except Exception as e:
        logger.warning("usage_callback_failed", err=str(e))
