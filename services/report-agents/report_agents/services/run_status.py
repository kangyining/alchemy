"""Per-run status store — GCS-backed with in-memory cache.

Reads are always served from in-memory cache (instant).
On first access per user, GCS is loaded in a background thread so the
first response is not blocked. Writes go to both cache and GCS.

Status files live at: gs://{REPORTS_BUCKET}/{user_id}/runs/{run_id}.json

Schema:
  {
    "run_id":       "20260408_143022",
    "status":       "in_progress" | "completed" | "failed",
    "started_at":   "<ISO-8601 UTC>",
    "completed_at": "<ISO-8601 UTC>",
    "pdf_filename": "financial_report_20260408_143022.pdf",
    "error":        "<message>"
  }
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STALENESS_SECONDS = 2 * 60 * 60 + 15 * 60  # 2h timeout + 15 min buffer

# In-memory cache: {user_id: {run_id: status_dict}}
_cache: dict[str, dict[str, dict]] = {}
# Per-user load events: set once GCS load completes (first call blocks, rest are instant)
_load_events: dict[str, threading.Event] = {}

_bucket = None


def _get_bucket():
    global _bucket
    if _bucket is not None:
        return _bucket
    bucket_name = os.environ.get("REPORTS_BUCKET")
    if not bucket_name:
        return None
    from google.cloud import storage as gcs
    _bucket = gcs.Client().bucket(bucket_name)
    return _bucket


def patch_status(user_id: str, run_id: str, updates: dict) -> None:
    """Merge updates into the existing status record without replacing other fields."""
    existing = _cache.get(user_id, {}).get(run_id, {})
    write_status(user_id, run_id, {**existing, **updates})


def write_status(user_id: str, run_id: str, data: dict) -> None:
    """Write status to cache (instant) and GCS (background thread)."""
    if user_id not in _cache:
        _cache[user_id] = {}
    _cache[user_id][run_id] = data

    bucket = _get_bucket()
    if not bucket:
        return

    blob_name = f"{user_id}/runs/{run_id}.json"
    payload = json.dumps(data)

    def _upload() -> None:
        try:
            bucket.blob(blob_name).upload_from_string(payload, content_type="application/json")
        except Exception as e:
            logger.warning("Failed to write run status for %s/%s: %s", user_id, run_id, e)

    threading.Thread(target=_upload, daemon=True).start()


def list_runs(user_id: str) -> list[dict]:
    """Return run status records for a user, newest first.

    First call per user blocks until GCS is loaded (ensures fresh data).
    All subsequent calls return instantly from cache.
    """
    if user_id not in _load_events:
        event = threading.Event()
        _load_events[user_id] = event
        threading.Thread(target=_load_user_from_gcs, args=(user_id, event), daemon=True).start()
    _load_events[user_id].wait(timeout=10)

    now = datetime.now(timezone.utc)
    runs: list[dict] = []

    for data in _cache.get(user_id, {}).values():
        if data.get("status") == "in_progress":
            try:
                started = datetime.fromisoformat(data["started_at"])
                if (now - started).total_seconds() > STALENESS_SECONDS:
                    data = {**data, "status": "failed", "error": "Run timed out (no response within 15 min)"}
            except Exception:
                pass
        runs.append(data)

    return sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)


def _load_user_from_gcs(user_id: str, event: threading.Event | None = None) -> None:
    bucket = _get_bucket()
    if not bucket:
        if event:
            event.set()
        return
    try:
        blobs = bucket.client.list_blobs(bucket.name, prefix=f"{user_id}/runs/")
        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue
            try:
                data = json.loads(blob.download_as_text())
                run_id = data.get("run_id")
                if run_id:
                    if user_id not in _cache:
                        _cache[user_id] = {}
                    _cache[user_id].setdefault(run_id, data)
            except Exception:
                continue
        logger.info("Loaded GCS history for %s", user_id)
    except Exception as e:
        logger.warning("Failed to load runs from GCS for %s: %s", user_id, e)
        _load_events.pop(user_id, None)  # allow retry on next call
    finally:
        if event:
            event.set()
