"""Метрики качества кадра и выявление перекрытия/засветки камеры."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

GRID = 4
THUMB_WIDTH = 320


@dataclass
class FrameQuality:
    mean: float
    std: float
    sharpness: float
    cell_mean: np.ndarray  # (GRID*GRID,)
    cell_std: np.ndarray   # (GRID*GRID,)


def make_thumbnail(image: np.ndarray) -> np.ndarray:
    """Уменьшенный кадр в оттенках серого — для метрик качества и сравнения зон."""
    height, width = image.shape[:2]
    scale = THUMB_WIDTH / float(width)
    small = cv2.resize(image, (THUMB_WIDTH, max(1, int(round(height * scale)))),
                       interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def measure_quality(gray: np.ndarray) -> FrameQuality:
    height, width = gray.shape
    cell_means, cell_stds = [], []
    for row in range(GRID):
        for col in range(GRID):
            cell = gray[row * height // GRID:(row + 1) * height // GRID,
                        col * width // GRID:(col + 1) * width // GRID]
            cell_means.append(float(cell.mean()))
            cell_stds.append(float(cell.std()))
    return FrameQuality(
        mean=float(gray.mean()),
        std=float(gray.std()),
        sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        cell_mean=np.array(cell_means),
        cell_std=np.array(cell_stds),
    )


def obstruction_mask(qualities: list[FrameQuality], cell_fraction: float) -> np.ndarray:
    """True для кадров, где обзор камеры перекрыт, кадр чёрный/засвечен или однороден.

    Сравнение идёт с медианным («нормальным») состоянием этого же видео, поэтому
    метод не зависит от освещения конкретной кассы.
    """
    if not qualities:
        return np.zeros(0, dtype=bool)
    means = np.array([q.mean for q in qualities])
    stds = np.array([q.std for q in qualities])
    sharpness = np.array([q.sharpness for q in qualities])
    cell_means = np.stack([q.cell_mean for q in qualities])
    cell_stds = np.stack([q.cell_std for q in qualities])

    ref_std = float(np.median(stds))
    ref_sharp = float(np.median(sharpness))
    ref_cell_mean = np.median(cell_means, axis=0)
    ref_cell_std = np.median(cell_stds, axis=0)

    # 1) Однородный кадр (крышка объектива, лист бумаги вплотную, чёрный/белый экран):
    #    либо абсолютно плоский, либо резко потерял контраст относительно обычного вида кассы
    flat = stds < 4.0
    uniform = flat | ((stds < 12.0) & (stds < 0.4 * max(ref_std, 1e-6)))
    # 2) Большая часть ячеек потеряла текстуру и сменила яркость (рука/предмет у объектива)
    lost_texture = cell_stds < np.maximum(0.35 * ref_cell_std, 3.0)
    shifted = np.abs(cell_means - ref_cell_mean) > 20.0
    partial = (lost_texture & shifted).mean(axis=1) >= cell_fraction
    # 3) Сильная расфокусировка/запотевание: резкость упала на порядок вместе с контрастом
    blurred = (sharpness < 0.1 * max(ref_sharp, 1e-6)) & (stds < 0.5 * max(ref_std, 1e-6))
    return uniform | partial | blurred
