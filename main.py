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
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app


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
