"""Кадры-доказательства: кэш кадров в JPEG, аннотирование и кодирование в base64."""

from __future__ import annotations

import base64

import cv2
import numpy as np

from .records import FrameRecord
from .zones import ZoneLayout

_RED = (40, 40, 230)
_GREEN = (80, 200, 80)
_BLUE = (230, 160, 40)
_GRAY = (190, 190, 190)


class FrameCache:
    """Хранит каждый проанализированный кадр в виде JPEG (≈100 КБ), чтобы не перечитывать видео."""

    def __init__(self, max_width: int, quality: int = 90):
        self.max_width = max_width
        self.quality = quality
        self.scale = 1.0
        self._frames: list[bytes] = []

    def add(self, image: np.ndarray) -> None:
        height, width = image.shape[:2]
        self.scale = min(1.0, self.max_width / float(width))
        if self.scale < 1.0:
            image = cv2.resize(image, (int(round(width * self.scale)), int(round(height * self.scale))),
                               interpolation=cv2.INTER_AREA)
        ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if not ok:
            raise RuntimeError("Не удалось закодировать кадр в JPEG")
        self._frames.append(buffer.tobytes())

    def jpeg(self, index: int) -> bytes:
        return self._frames[index]

    def image(self, index: int) -> np.ndarray:
        return cv2.imdecode(np.frombuffer(self._frames[index], dtype=np.uint8), cv2.IMREAD_COLOR)

    def __len__(self) -> int:
        return len(self._frames)


def _label(image: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = origin
    y = max(y, th + baseline + 2)
    cv2.rectangle(image, (x, y - th - baseline - 2), (x + tw + 4, y), color, -1)
    cv2.putText(image, text, (x + 2, y - baseline), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def _polyline(image: np.ndarray, polygon: np.ndarray | None, scale: float, color) -> None:
    if polygon is None or len(polygon) < 3:
        return
    points = np.round(polygon * scale).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(image, [points], True, color, 1, cv2.LINE_AA)


def render_evidence(cache: FrameCache, record: FrameRecord, layout: ZoneLayout | None,
                    highlights: list, caption: str, annotate: bool, quality: int,
                    workplace: tuple[tuple[float, float], float] | None = None) -> str:
    """JPEG кадра в base64. При annotate — рабочее место/зоны, люди и выделение объекта нарушения."""
    if not annotate:
        return base64.b64encode(cache.jpeg(record.index)).decode("ascii")

    image = cache.image(record.index)
    scale = cache.scale
    if workplace is not None:
        (cx, cy), radius = workplace
        cv2.ellipse(image, (int(cx * scale), int(cy * scale)), (int(radius * scale), int(radius * scale * 0.5)),
                    0, 0, 360, _GREEN, 1, cv2.LINE_AA)
    elif layout is not None:
        _polyline(image, layout.workplace, scale, _GREEN)
        _polyline(image, layout.client_counter, scale, _BLUE)
    for person in record.persons:
        x1, y1, x2, y2 = (int(round(v * scale)) for v in person.box)
        cv2.rectangle(image, (x1, y1), (x2, y2), _GRAY, 1, cv2.LINE_AA)
    for box, text in highlights:
        x1, y1, x2, y2 = (int(round(v * scale)) for v in box)
        cv2.rectangle(image, (x1, y1), (x2, y2), _RED, 2, cv2.LINE_AA)
        _label(image, text, (x1, y1), _RED)

    header = f"{caption}  t={record.time_sec:.2f}s"
    _label(image, header, (6, 22), (30, 30, 30))
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Не удалось закодировать кадр-доказательство")
    return base64.b64encode(buffer.tobytes()).decode("ascii")
