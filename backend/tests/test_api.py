from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from app.pipeline.analyzer import VideoAnalyzer
from app.pipeline.rule_config import RuleConfig

from .conftest import ColorBlobDetector

KEY = "test-key-123"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEY", KEY)
    settings = replace(load_settings(), data_dir=tmp_path / "data", max_concurrent_jobs=1)
    analyzer = VideoAnalyzer(ColorBlobDetector(), RuleConfig())
    with TestClient(create_app(settings, analyzer)) as test_client:
        yield test_client


def _wait(client: TestClient, job_id: str, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": KEY})
        assert response.status_code == 200
        body = response.json()
        if body["status"] != "processing":
            return body
        assert 0.0 <= body["progress"] <= 1.0
        time.sleep(0.2)
    raise AssertionError("задача не завершилась вовремя")


def test_requires_api_key(client: TestClient, scene_video: Path):
    with scene_video.open("rb") as handle:
        response = client.post("/api/v1/analyze", files={"file": ("a.mov", handle, "video/quicktime")})
    assert response.status_code == 401
    assert client.get("/api/v1/jobs/abc", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/health").status_code == 200


def test_full_flow(client: TestClient, scene_video: Path):
    with scene_video.open("rb") as handle:
        response = client.post("/api/v1/analyze", headers={"X-API-Key": KEY},
                               files={"file": ("video_017.mov", handle, "video/quicktime")})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    body = _wait(client, job_id)
    assert body["status"] == "done", body
    assert body["job_id"] == job_id
    assert body["verdict"] == "violation"
    assert list(body)[:4] == ["job_id", "status", "verdict", "violations"]
    violation = body["violations"][0]
    for key in ("type", "timecode_sec", "description", "evidence_frames"):
        assert key in violation
    frame = violation["evidence_frames"][0]
    assert set(frame) == {"timestamp_sec", "image_base64"}
    assert frame["image_base64"].startswith("/9j/")  # JPEG в base64


def test_rejects_wrong_extension(client: TestClient):
    response = client.post("/api/v1/analyze", headers={"X-API-Key": KEY},
                           files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_broken_video_fails_gracefully(client: TestClient):
    response = client.post("/api/v1/analyze", headers={"X-API-Key": KEY},
                           files={"file": ("broken.mov", b"not a video at all" * 100, "video/quicktime")})
    assert response.status_code == 200
    body = _wait(client, response.json()["job_id"])
    assert body["status"] == "failed"
    assert body["error"]


def test_unknown_job(client: TestClient):
    assert client.get("/api/v1/jobs/deadbeef", headers={"X-API-Key": KEY}).status_code == 404


def test_violation_types(client: TestClient):
    response = client.get("/api/v1/violation-types", headers={"X-API-Key": KEY})
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert {"WORKPLACE_ABANDONED", "MOBILE_PHONE", "CAMERA_OBSTRUCTION"} <= codes
