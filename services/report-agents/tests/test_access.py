import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access import ReportAccessMiddleware
from routes import install_report_routes

USER = "u_" + "a" * 64
OTHER = "u_" + "b" * 64


class Blob:
    def __init__(self, name):
        self.name = name

    def exists(self):
        return self.name == f"{USER}/fixture.pdf"

    def download_as_bytes(self):
        return b"%PDF-synthetic-fixture"


class Bucket:
    def blob(self, name):
        return Blob(name)


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"API_KEY": "synthetic-service-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = FastAPI()
        self.app.add_middleware(ReportAccessMiddleware)
        install_report_routes(self.app, lambda user: [{"run_id": "fixture", "status": "completed"}], Bucket)

        @self.app.post("/apps/report_agents/users/{user}/sessions/{session}")
        async def session(user: str, session: str):
            return {"userId": user, "id": session}

        @self.app.post("/run_sse")
        async def run(request: Request):
            body = await request.json()
            self.assertEqual(body["newMessage"]["parts"][0]["inlineData"]["data"], "c3ludGhldGlj")
            return StreamingResponse(iter(['data: {"status":"completed"}\n\n']), media_type="text/event-stream")

        self.client = TestClient(self.app)
        self.headers = {"X-API-Key": "synthetic-service-secret", "X-Report-User": USER}

    def test_service_fails_closed_and_requires_verified_identity(self):
        url = f"/reports/{USER}"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers={"X-API-Key": "synthetic-service-secret"}).status_code, 401)
        with patch.dict(os.environ, {"API_KEY": ""}):
            self.assertEqual(self.client.get(url, headers=self.headers).status_code, 503)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_ownership_applies_to_history_downloads_sessions_and_runs(self):
        for url in (f"/reports/{OTHER}", f"/reports/{OTHER}/fixture.pdf"):
            self.assertEqual(self.client.get(url, headers=self.headers).status_code, 403)
        self.assertEqual(self.client.post(f"/apps/report_agents/users/{OTHER}/sessions/fixture", headers=self.headers, json={}).status_code, 403)
        self.assertEqual(self.client.post("/run_sse", headers=self.headers, json={"appName": "report_agents", "userId": OTHER, "sessionId": "fixture"}).status_code, 403)
        self.assertEqual(self.client.post("/run_sse", headers=self.headers, content="invalid-json").status_code, 400)

    def test_synthetic_upload_stream_history_and_download(self):
        created = self.client.post(f"/apps/report_agents/users/{USER}/sessions/fixture", headers=self.headers, json={})
        self.assertEqual(created.status_code, 200)
        result = self.client.post("/run_sse", headers=self.headers, json={
            "appName": "report_agents", "userId": USER, "sessionId": "fixture",
            "newMessage": {"parts": [{"inlineData": {"data": "c3ludGhldGlj", "mimeType": "text/plain"}}]},
        })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIn('data: {"status":"completed"}', result.text)
        self.assertEqual(self.client.get(f"/reports/{USER}", headers=self.headers).json()[0]["status"], "completed")
        downloaded = self.client.get(f"/reports/{USER}/fixture.pdf", headers=self.headers)
        self.assertEqual(downloaded.content, b"%PDF-synthetic-fixture")
        self.assertEqual(downloaded.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get(f"/reports/{USER}/missing.pdf", headers=self.headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
