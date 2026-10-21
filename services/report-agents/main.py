"""ASGI entrypoint for Hypercorn / uvicorn (ADK FastAPI app).

Hypercorn negotiates HTTP/2 over TLS via ALPN (h2). Uvicorn 0.40+ no longer
exposes ``--http2`` on the CLI; use Hypercorn in Docker and for local HTTP/2:

  hypercorn main:app -b 0.0.0.0:8443 --certfile cert.pem --keyfile key.pem

Deploy with ``gcloud run deploy ... --use-http2`` so Cloud Run speaks h2c to the
container; without it, traffic to the app is HTTP/1.1 even if clients use HTTP/2
at the edge.
"""

from __future__ import annotations

import os
import signal
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from access import ReportAccessMiddleware
from routes import install_report_routes
from google.adk.cli.fast_api import get_fast_api_app

logger = logging.getLogger(__name__)


def _agents_dir() -> str:
    return os.environ.get("ADK_AGENTS_DIR", str(Path(__file__).resolve().parent))


def _port() -> int:
    return int(os.environ.get("PORT", "8000"))


app = get_fast_api_app(
    agents_dir=_agents_dir(),
    web=False,
    host=os.environ.get("HOST", "0.0.0.0"),
    port=_port(),
    a2a=os.environ.get("ADK_A2A", "").lower() in ("1", "true", "yes"),
    reload_agents=os.environ.get("ADK_RELOAD_AGENTS", "").lower() in ("1", "true", "yes"),
)
app.add_middleware(ReportAccessMiddleware)


def _fail_all_in_progress() -> None:
    """Mark all in_progress runs as failed â€” called on SIGTERM before shutdown."""
    from report_agents.services.run_status import _cache, write_status
    now = datetime.now(timezone.utc).isoformat()
    for user_id, runs in _cache.items():
        for run_id, data in runs.items():
            if data.get("status") == "in_progress":
                write_status(user_id, run_id, {
                    **data,
                    "status": "failed",
                    "completed_at": now,
                    "error": "Server shutting down",
                })
                logger.info("Marked run %s/%s as failed on shutdown", user_id, run_id)


def _sigterm_handler(signum, frame) -> None:
    _fail_all_in_progress()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _sigterm_handler)

# Pre-warm GCS client at startup so first request isn't slow
threading.Thread(target=lambda: __import__(
    'report_agents.services.run_status', fromlist=['_get_bucket']
)._get_bucket(), daemon=True).start()


_gcs_client = None


def _gcs_bucket():
    global _gcs_client
    bucket_name = os.environ.get("REPORTS_BUCKET")
    if not bucket_name:
        raise HTTPException(status_code=503, detail="REPORTS_BUCKET not configured")
    from google.cloud import storage as gcs
    if _gcs_client is None:
        _gcs_client = gcs.Client()
    return _gcs_client.bucket(bucket_name)


def _list_runs(user_id: str):
    from report_agents.services.run_status import list_runs
    return list_runs(user_id)


install_report_routes(app, _list_runs, _gcs_bucket)
