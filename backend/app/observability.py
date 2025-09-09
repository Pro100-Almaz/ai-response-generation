import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter

logger = structlog.get_logger()

REQ_COUNTER = Counter("http_requests_total", "Total HTTP Requests", ["method", "path", "status"])
REQ_LATENCY = Histogram("http_request_latency_seconds", "Request latency", ["method", "path"])

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            latency = time.perf_counter() - start
            path = request.url.path
            method = request.method
            status = getattr(request.state, "status_code", 200)
            REQ_COUNTER.labels(method, path, status).inc()
            REQ_LATENCY.labels(method, path).observe(latency)

metrics_router = APIRouter()

@metrics_router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
