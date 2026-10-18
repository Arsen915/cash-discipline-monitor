"""Структуры данных, которые пайплайн накапливает по каждому проанализированному кадру."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import box_center, box_diag
from .quality import FrameQuality


@dataclass
class PersonObs:
    track_id: int
    box: tuple[float, float, float, float]
    confidence: float

    @property
    def center(self) -> np.ndarray:
        return box_center(self.box)

    @property
    def diag(self) -> float:
        return box_diag(self.box)


@dataclass
class ObjectObs:
    label: str
    box: tuple[float, float, float, float]
    confidence: float

    @property
    def center(self) -> np.ndarray:
        return box_center(self.box)


@dataclass
class FrameRecord:
    index: int          # порядковый номер среди проанализированных кадров
    frame_index: int    # номер кадра в видео
    time_sec: float
    persons: list[PersonObs]
    objects: list[ObjectObs]
    quality: FrameQuality
    thumb: np.ndarray   # серый уменьшенный кадр (ширина quality.THUMB_WIDTH)


@dataclass
class FrameState:
    """Интерпретация кадра относительно зон кассы (заполняется после калибровки)."""

    valid: bool = True                       # кадр пригоден для анализа (обзор не перекрыт)
    cashier_present: bool = False            # кто-то находится на рабочем месте кассира
    client_present: bool = False             # клиент у стойки
    cashier_side: list[int] = field(default_factory=list)   # индексы persons за стойкой
    client_side: list[int] = field(default_factory=list)    # индексы persons в клиентской зоне
    phones: list[int] = field(default_factory=list)         # индексы objects: телефоны за стойкой
    bags: list[int] = field(default_factory=list)           # индексы objects: сумки за стойкой
    phones_in_hand: list[int] = field(default_factory=list) # из phones: телефон в руке кассира
    fixtures: list[int] = field(default_factory=list)       # оборудование, принятое за сумку/телефон
