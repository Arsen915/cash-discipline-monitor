"""Синтетическая сцена кассы и детектор по цвету для детерминированных тестов правил.

Сцена 20 с (вид сверху, 640x360): кассир (зелёный блок) сверху, клиент снизу.
* 0–6 с и 11–20 с кассир на месте; клиент у стойки 3–18 с → уход кассира в 6.0 с;
* 13–16 с у кассира в руке телефон (красный блок);
* 17–19 с камера перекрыта (тёмный кадр).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.pipeline.detector import Detection, Detector

FPS = 30
SIZE = (640, 360)
DURATION = 20.0
CASHIER_BOX = (280, 40, 360, 140)
CLIENT_BOX = (280, 200, 360, 300)
PHONE_BOX = (370, 80, 395, 96)


def background(seed: int = 7) -> np.ndarray:
    """Серый текстурный фон «помещения»: шум + мебель разной яркости (без насыщенных цветов)."""
    rng = np.random.default_rng(seed)
    gray = cv2.GaussianBlur(rng.integers(40, 220, size=(SIZE[1], SIZE[0]), dtype=np.uint8), (0, 0), 1.2)
    for _ in range(12):
        x, y = int(rng.integers(0, SIZE[0] - 60)), int(rng.integers(0, SIZE[1] - 40))
        cv2.rectangle(gray, (x, y), (x + int(rng.integers(20, 120)), y + int(rng.integers(10, 80))),
                      int(rng.integers(20, 235)), -1)
    cv2.rectangle(gray, (200, 150), (440, 185), 120, -1)  # стойка
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def render_scene(path: Path) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, SIZE)
    assert writer.isOpened()
    scene = background()
    for index in range(int(DURATION * FPS)):
        t = index / FPS
        if 17.0 <= t < 19.0:
            frame = np.full_like(scene, 5)
        else:
            frame = scene.copy()
            if t < 6.0 or t >= 11.0:
                cv2.rectangle(frame, CASHIER_BOX[:2], CASHIER_BOX[2:], (0, 255, 0), -1)
            if 3.0 <= t < 18.0:
                cv2.rectangle(frame, CLIENT_BOX[:2], CLIENT_BOX[2:], (0, 255, 0), -1)
            if 13.0 <= t < 16.0:
                cv2.rectangle(frame, PHONE_BOX[:2], PHONE_BOX[2:], (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    return path


class ColorBlobDetector(Detector):
    """Детектор по цвету вместо нейросети в юнит-тестах.

    Зелёный — человек, красный — телефон, жёлтый — рюкзак (уверенно), синий — «suitcase»
    с низкой уверенностью (так модель видит принтер), пурпурный — «cell phone» с низкой
    уверенностью (так модель видит денежный терминал).
    """

    name = "color-blob (test)"

    def detect(self, image: np.ndarray) -> list[Detection]:
        b, g, r = (image[..., i].astype(int) for i in range(3))
        result: list[Detection] = []
        for label, confidence, mask in (
            ("person", 0.9, (g > 180) & (r < 90) & (b < 90)),
            ("cell phone", 0.8, (r > 180) & (g < 90) & (b < 90)),
            ("backpack", 0.8, (r > 180) & (g > 180) & (b < 90)),
            ("suitcase", 0.45, (b > 180) & (g < 90) & (r < 90)),
            ("cell phone", 0.5, (r > 180) & (b > 180) & (g < 90)),
        ):
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w * h >= 60:
                    result.append(Detection(label, confidence,
                                            (float(x), float(y), float(x + w), float(y + h))))
        return result


@pytest.fixture(scope="session")
def scene_video(tmp_path_factory) -> Path:
    return render_scene(tmp_path_factory.mktemp("video") / "scene.mov")
