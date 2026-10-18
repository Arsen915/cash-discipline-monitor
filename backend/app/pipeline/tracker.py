"""Простой трекер людей: жадное сопоставление по IoU и расстоянию между центрами.

Для одной камеры над кассой с 1–4 людьми в кадре этого достаточно: id нужны,
чтобы понять, откуда человек пришёл (из клиентской зоны или нет), и для
автокалибровки зон. Идентификация личности (распознавание лиц) не выполняется.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .geometry import Box, box_center, box_diag, box_iou


@dataclass
class _Track:
    track_id: int
    box: np.ndarray
    last_time: float
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(2))


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.15, max_center_shift: float = 0.9,
                 max_age_sec: float = 2.0):
        self.iou_threshold = iou_threshold
        # Максимальный сдвиг центра в долях диагонали бокса (для сопоставления без перекрытия)
        self.max_center_shift = max_center_shift
        self.max_age_sec = max_age_sec
        self._tracks: list[_Track] = []
        self._next_id = 1

    def update(self, time_sec: float, boxes: Sequence[Box]) -> list[int]:
        self._tracks = [t for t in self._tracks if time_sec - t.last_time <= self.max_age_sec]
        candidates: list[tuple[float, int, int]] = []
        for ti, track in enumerate(self._tracks):
            dt = max(time_sec - track.last_time, 1e-3)
            predicted_center = box_center(track.box) + track.velocity * dt
            track_diag = box_diag(track.box)
            for di, box in enumerate(boxes):
                iou = box_iou(track.box, box)
                shift = np.linalg.norm(box_center(box) - predicted_center) / max(
                    (track_diag + box_diag(box)) / 2.0, 1.0)
                if iou >= self.iou_threshold:
                    score = 1.0 + iou
                elif shift <= self.max_center_shift:
                    score = 1.0 - shift / self.max_center_shift
                else:
                    continue
                candidates.append((score, ti, di))

        assigned: list[int] = [0] * len(boxes)
        used_tracks: set[int] = set()
        for _, ti, di in sorted(candidates, reverse=True):
            if ti in used_tracks or assigned[di]:
                continue
            track = self._tracks[ti]
            new_box = np.asarray(boxes[di], dtype=np.float64)
            dt = max(time_sec - track.last_time, 1e-3)
            velocity = (box_center(new_box) - box_center(track.box)) / dt
            track.velocity = 0.6 * track.velocity + 0.4 * velocity
            track.box = new_box
            track.last_time = time_sec
            assigned[di] = track.track_id
            used_tracks.add(ti)

        for di, box in enumerate(boxes):
            if assigned[di]:
                continue
            track = _Track(self._next_id, np.asarray(box, dtype=np.float64), time_sec)
            self._next_id += 1
            self._tracks.append(track)
            assigned[di] = track.track_id
        return assigned
