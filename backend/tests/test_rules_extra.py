"""Оборудование, похожее на сумку/телефон, телефон в руке, рюкзак и отлучка во время смены."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.pipeline.analyzer import VideoAnalyzer
from app.pipeline.rule_config import RuleConfig
from app.pipeline.rules import overhead_rules

from .conftest import CASHIER_BOX, CLIENT_BOX, background

GREEN, RED, YELLOW, BLUE, MAGENTA = (0, 255, 0), (0, 0, 255), (0, 255, 255), (255, 0, 0), (255, 0, 255)
PRINTER_BOX = (400, 50, 470, 110)     # справа от кассира, на столе
TERMINAL_BOX = (220, 110, 250, 130)   # слева от кассира, на столе
BACKPACK_BOX = (200, 40, 250, 90)
HAND_PHONE_BOX = (340, 90, 365, 106)  # перекрывает бокс кассира


def render(path: Path, duration: float, items) -> Path:
    """items: (бокс, цвет, начало, конец) — прямоугольник рисуется на интервале [начало, конец)."""
    fps = 15
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 360))
    scene = background(seed=3)
    for index in range(int(duration * fps)):
        t = index / fps
        frame = scene.copy()
        for box, color, start, end in items:
            if start <= t < end:
                cv2.rectangle(frame, box[:2], box[2:], color, -1)
        writer.write(frame)
    writer.release()
    return path


def analyze(path: Path) -> dict[str, list[dict]]:
    result = VideoAnalyzer(_detector(), RuleConfig(), analysis_fps=3.0, rules=overhead_rules()).analyze(path)
    grouped: dict[str, list[dict]] = {}
    for violation in result["violations"]:
        grouped.setdefault(violation["code"], []).append(violation)
    return grouped


def _detector():
    from .conftest import ColorBlobDetector
    return ColorBlobDetector()


def staffed(duration: float, *extra):
    """Кассир на месте всю запись, клиент у стойки большую часть времени."""
    return [(CASHIER_BOX, GREEN, 0, duration), (CLIENT_BOX, GREEN, 3, duration - 3), *extra]


def test_printer_is_not_a_personal_bag(tmp_path: Path):
    path = render(tmp_path / "printer.mov", 30, staffed(30, (PRINTER_BOX, BLUE, 0, 30)))
    assert "PERSONAL_BELONGINGS" not in analyze(path)


def test_card_terminal_is_not_a_phone(tmp_path: Path):
    path = render(tmp_path / "terminal.mov", 30, staffed(30, (TERMINAL_BOX, MAGENTA, 0, 30)))
    assert "MOBILE_PHONE" not in analyze(path)


def test_backpack_brought_in_is_reported(tmp_path: Path):
    path = render(tmp_path / "backpack.mov", 30, staffed(30, (BACKPACK_BOX, YELLOW, 8, 22)))
    found = analyze(path)["PERSONAL_BELONGINGS"]
    assert abs(found[0]["timecode_sec"] - 8.0) <= 0.7


def test_confident_backpack_all_shift_is_still_reported(tmp_path: Path):
    path = render(tmp_path / "backpack_all.mov", 30, staffed(30, (BACKPACK_BOX, YELLOW, 0, 30)))
    assert "PERSONAL_BELONGINGS" in analyze(path)


def test_short_phone_in_hand_is_reported(tmp_path: Path):
    path = render(tmp_path / "hand.mov", 20, staffed(20, (HAND_PHONE_BOX, RED, 10, 10.8)))
    found = analyze(path)["MOBILE_PHONE"]
    assert "в руке кассира" in found[0]["description"]


def test_workplace_left_during_shift(tmp_path: Path):
    items = [
        (CASHIER_BOX, GREEN, 0, 10), (CASHIER_BOX, GREEN, 50, 60),
        (CLIENT_BOX, GREEN, 2, 8), (CLIENT_BOX, GREEN, 52, 58),
    ]
    found = analyze(render(tmp_path / "left.mov", 60, items))
    assert "WORKPLACE_ABANDONED" not in found
    event = found["WORKPLACE_LEFT"][0]
    assert abs(event["timecode_sec"] - 10.0) <= 0.7
    assert abs(event["end_sec"] - 50.0) <= 1.0
    assert 2 <= len(event["evidence_frames"]) <= 3


def test_short_break_is_not_reported(tmp_path: Path):
    items = [
        (CASHIER_BOX, GREEN, 0, 10), (CASHIER_BOX, GREEN, 25, 40),
        (CLIENT_BOX, GREEN, 2, 8), (CLIENT_BOX, GREEN, 30, 36),
    ]
    found = analyze(render(tmp_path / "short.mov", 40, items))
    assert "WORKPLACE_LEFT" not in found
    assert np.all([code != "WORKPLACE_ABANDONED" for code in found])
