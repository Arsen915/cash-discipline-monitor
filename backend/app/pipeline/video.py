"""Чтение видео через OpenCV: метаданные и равномерная по времени выборка кадров."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


class VideoError(RuntimeError):
    """Видео не удалось открыть или декодировать."""


@dataclass(frozen=True)
class VideoMeta:
    fps: float
    frame_count: int
    width: int
    height: int
    duration_sec: float
    codec: str


@dataclass
class SampledFrame:
    frame_index: int
    time_sec: float
    image: np.ndarray


def _open(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise VideoError("Не удалось открыть видеофайл: формат не поддерживается или файл повреждён")
    return cap


def _fourcc_to_str(value: float) -> str:
    code = int(value)
    text = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    return text if text.isprintable() and text.strip() else "unknown"


def _sane_fps(value: float) -> float:
    return value if math.isfinite(value) and 1.0 < value <= 240.0 else 30.0


def probe_video(path: Path) -> VideoMeta:
    cap = _open(path)
    try:
        fps = _sane_fps(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise VideoError("Видео не содержит декодируемых кадров")
        # Берём размер с реального кадра: OpenCV уже применил поворот из метаданных .mov
        height, width = frame.shape[:2]
        codec = _fourcc_to_str(cap.get(cv2.CAP_PROP_FOURCC))
    finally:
        cap.release()
    duration = frame_count / fps if frame_count > 0 else 0.0
    return VideoMeta(fps=fps, frame_count=max(frame_count, 0), width=width, height=height,
                     duration_sec=duration, codec=codec)


class FrameSampler:
    """Последовательно декодирует видео и отдаёт кадры с шагом ``step_sec`` по времени.

    Кадры между выборками только «грабятся» (без конвертации в BGR), что заметно
    быстрее полного чтения. Поле ``step_sec`` можно увеличить во время итерации —
    так анализатор укладывается в бюджет времени на длинных видео.
    """

    def __init__(self, path: Path, fps: float, step_sec: float):
        self.path = path
        self.fps = _sane_fps(fps)
        self.step_sec = max(step_sec, 1.0 / self.fps)
        self.frames_decoded = 0

    def __iter__(self) -> Iterator[SampledFrame]:
        cap = _open(self.path)
        try:
            next_time = 0.0
            index = -1
            # Берём кадр, ближайший к плановому моменту; расписание не «плывёт» от округлений
            tolerance = 0.5 / self.fps - 1e-6
            while cap.grab():
                index += 1
                self.frames_decoded = index + 1
                time_sec = index / self.fps
                if time_sec < next_time - tolerance:
                    continue
                ok, image = cap.retrieve()
                if not ok or image is None:
                    continue
                yield SampledFrame(frame_index=index, time_sec=time_sec, image=image)
                next_time += self.step_sec
                if next_time <= time_sec:
                    next_time = time_sec + self.step_sec
        finally:
            cap.release()
