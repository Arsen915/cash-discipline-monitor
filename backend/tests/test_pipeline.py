from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.pipeline.analyzer import VideoAnalyzer
from app.pipeline.detector import YoloxOnnxDetector
from app.pipeline.rule_config import RuleConfig
from app.pipeline.rules import overhead_rules
from app.pipeline.video import FrameSampler, probe_video

from .conftest import DURATION, ColorBlobDetector, background


def _by_code(result: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for violation in result["violations"]:
        grouped.setdefault(violation["code"], []).append(violation)
    return grouped


def test_sampler_keeps_schedule(scene_video: Path):
    meta = probe_video(scene_video)
    assert meta.width == 640 and meta.height == 360
    times = [f.time_sec for f in FrameSampler(scene_video, meta.fps, 0.25)]
    assert len(times) == int(DURATION / 0.25)
    assert np.allclose(np.diff(times), 0.25, atol=0.02)


@pytest.fixture(scope="module")
def scene_result(scene_video: Path) -> dict:
    analyzer = VideoAnalyzer(ColorBlobDetector(), RuleConfig(), analysis_fps=3.0)
    return analyzer.analyze(scene_video, debug=True)


def test_verdict_and_types(scene_result: dict):
    assert scene_result["verdict"] == "violation"
    codes = _by_code(scene_result)
    assert set(codes) == {"WORKPLACE_LEFT_UNSECURED", "MOBILE_PHONE", "CAMERA_OBSTRUCTION"}, codes.keys()
    assert scene_result["analysis"]["layout"]["source"] == "auto"


@pytest.mark.parametrize("code, expected", [
    ("WORKPLACE_LEFT_UNSECURED", 6.0),
    ("MOBILE_PHONE", 13.0),
    ("CAMERA_OBSTRUCTION", 17.0),
])
def test_timecodes(scene_result: dict, code: str, expected: float):
    violation = _by_code(scene_result)[code][0]
    assert abs(violation["timecode_sec"] - expected) <= 0.35
    assert violation["evidence_frames"][0]["timestamp_sec"] == pytest.approx(violation["timecode_sec"])


def test_evidence_frames_are_jpeg(scene_result: dict):
    for violation in scene_result["violations"]:
        frames = violation["evidence_frames"]
        assert 1 <= len(frames) <= 3
        for frame in frames:
            raw = base64.b64decode(frame["image_base64"])
            assert raw[:2] == b"\xff\xd8"  # сигнатура JPEG
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            assert image is not None and image.shape[1] <= 960
        assert violation["rule"]["url"].startswith("https://adilet.zan.kz/")
        assert "Основание:" in violation["description"]


def test_manual_zones(scene_video: Path, tmp_path: Path):
    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({
        "cashier_side": [[0, 0], [1, 0], [1, 0.47], [0, 0.47]],
        "workplace": [[0.3, 0.0], [0.7, 0.0], [0.7, 0.47], [0.3, 0.47]],
        "client_counter": [[0.2, 0.47], [0.8, 0.47], [0.8, 1.0], [0.2, 1.0]],
    }), encoding="utf-8")
    result = VideoAnalyzer(ColorBlobDetector(), RuleConfig(), zones_file=zones,
                           rules=overhead_rules()).analyze(scene_video)
    assert result["analysis"]["layout"]["source"] == "manual"
    assert set(_by_code(result)) == {"WORKPLACE_ABANDONED", "MOBILE_PHONE", "CAMERA_OBSTRUCTION"}


def test_clean_video_has_no_violations(tmp_path: Path):
    path = tmp_path / "clean.mov"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    scene = background(seed=1)
    for index in range(300):
        frame = scene.copy()
        cv2.rectangle(frame, (280, 40), (360, 140), (0, 255, 0), -1)
        if 60 <= index < 240:
            cv2.rectangle(frame, (280, 200), (360, 300), (0, 255, 0), -1)
        writer.write(frame)
    writer.release()
    result = VideoAnalyzer(ColorBlobDetector(), RuleConfig()).analyze(path)
    assert result["verdict"] == "no_violation"
    assert result["violations"] == []


class _SlowDetector(ColorBlobDetector):
    def detect(self, image):
        time.sleep(0.05)
        return super().detect(image)


def test_sampling_adapts_to_budget(scene_video: Path):
    started = time.monotonic()
    result = VideoAnalyzer(_SlowDetector(), RuleConfig(), analysis_fps=3.0, budget_sec=2.0).analyze(scene_video)
    elapsed = time.monotonic() - started
    # Без адаптации: 60 кадров × 0.05 с = 3 с; с адаптацией шаг растёт и анализ укладывается в бюджет
    assert result["video"]["sampling_step_sec"] > 0.34
    assert result["video"]["frames_analyzed"] < 60
    assert elapsed < 2.5


def _model_path() -> Path | None:
    candidates = [os.environ.get("MODEL_PATH"),
                  str(Path(__file__).resolve().parents[1] / "models" / "yolox_tiny.onnx")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


@pytest.mark.skipif(_model_path() is None, reason="веса YOLOX не скачаны")
def test_real_detector_end_to_end(scene_video: Path):
    config = RuleConfig()
    detector = YoloxOnnxDetector(_model_path(), config.detector_labels, config.detector_min_conf)
    result = VideoAnalyzer(detector, config).analyze(scene_video)
    # Нейросеть не видит людей в цветных блоках, но перекрытие камеры должна найти любая модель
    assert "CAMERA_OBSTRUCTION" in _by_code(result)
