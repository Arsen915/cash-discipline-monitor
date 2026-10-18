"""Геометрические примитивы: боксы, полигоны, полуплоскости."""

from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

Box = Sequence[float]  # x1, y1, x2, y2


def box_center(box: Box) -> np.ndarray:
    return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0], dtype=np.float64)


def box_diag(box: Box) -> float:
    return float(np.hypot(box[2] - box[0], box[3] - box[1]))


def box_area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def box_iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def box_intersection_area(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def point_in_polygon(polygon: np.ndarray | None, point: Sequence[float]) -> bool:
    if polygon is None or len(polygon) < 3:
        return False
    contour = polygon.astype(np.float32).reshape(-1, 1, 2)
    return cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0


def polygon_bbox(polygon: np.ndarray) -> tuple[float, float, float, float]:
    return (float(polygon[:, 0].min()), float(polygon[:, 1].min()),
            float(polygon[:, 0].max()), float(polygon[:, 1].max()))


def frame_polygon(width: int, height: int) -> np.ndarray:
    return np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float64)


def circle_polygon(center: Sequence[float], radius: float, points: int = 36) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, points, endpoint=False)
    return np.column_stack([center[0] + radius * np.cos(angles), center[1] + radius * np.sin(angles)])


def clip_halfplane(polygon: np.ndarray, normal: np.ndarray, offset: float) -> np.ndarray:
    """Оставляет часть выпуклого полигона, где dot(p, normal) <= offset (Сазерленд–Ходжмен)."""
    if len(polygon) == 0:
        return polygon
    result: list[np.ndarray] = []
    count = len(polygon)
    for i in range(count):
        current, following = polygon[i], polygon[(i + 1) % count]
        d_current = float(np.dot(current, normal) - offset)
        d_following = float(np.dot(following, normal) - offset)
        if d_current <= 0:
            result.append(current)
        if d_current * d_following < 0:
            ratio = d_current / (d_current - d_following)
            result.append(current + ratio * (following - current))
    return np.array(result, dtype=np.float64).reshape(-1, 2)


def clip_to_frame(polygon: np.ndarray, width: int, height: int) -> np.ndarray:
    clipped = clip_halfplane(polygon, np.array([-1.0, 0.0]), 0.0)
    clipped = clip_halfplane(clipped, np.array([1.0, 0.0]), width - 1.0)
    clipped = clip_halfplane(clipped, np.array([0.0, -1.0]), 0.0)
    return clip_halfplane(clipped, np.array([0.0, 1.0]), height - 1.0)


def oriented_rect(origin: np.ndarray, axis: np.ndarray, along: tuple[float, float],
                  across: tuple[float, float]) -> np.ndarray:
    """Прямоугольник в системе координат (axis, перпендикуляр к axis) с началом в origin."""
    perp = np.array([-axis[1], axis[0]])
    corners = [(along[0], across[0]), (along[1], across[0]), (along[1], across[1]), (along[0], across[1])]
    return np.array([origin + axis * s + perp * t for s, t in corners], dtype=np.float64)
