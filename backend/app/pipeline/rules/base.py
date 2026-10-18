"""Общие типы и временные утилиты для правил."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from ..records import FrameRecord, FrameState
from ..room import Room
from ..rule_config import RuleConfig
from ..zones import ZoneLayout
from .catalog import ViolationType

Highlight = tuple[tuple[float, float, float, float], str]  # (бокс в координатах кадра, подпись)


@dataclass
class EvidenceRef:
    record_index: int
    highlights: list[Highlight] = field(default_factory=list)


@dataclass
class Event:
    vtype: ViolationType
    start_sec: float
    end_sec: float
    timecode_sec: float
    confidence: float
    description: str
    evidence: list[EvidenceRef]


@dataclass
class RuleContext:
    records: list[FrameRecord]
    states: list[FrameState]
    layout: ZoneLayout | None
    config: RuleConfig
    duration_sec: float
    step_sec: float
    room: "Room | None" = None

    @property
    def times(self) -> np.ndarray:
        return np.array([r.time_sec for r in self.records])

    @property
    def valid(self) -> np.ndarray:
        return np.array([s.valid for s in self.states], dtype=bool)


class Rule(ABC):
    vtype: ViolationType
    uses_room: bool = False  # правило опирается на модель помещения (room.py), а не на зоны стойки

    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> list[Event]:
        """Найденные события этого типа."""


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Отрезки подряд идущих True: список (start, end) с end не включительно."""
    result: list[tuple[int, int]] = []
    start = None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            result.append((start, i))
            start = None
    if start is not None:
        result.append((start, len(mask)))
    return result


def fill_gaps(mask: np.ndarray, times: np.ndarray, max_gap_sec: float) -> np.ndarray:
    """Закрывает «дыры» из False длительностью не более max_gap_sec между двумя True."""
    filled = mask.copy()
    for start, end in runs(~mask):
        if start == 0 or end == len(mask):
            continue
        if times[end] - times[start - 1] <= max_gap_sec + 1e-6:
            filled[start:end] = True
    return filled


def run_duration(times: np.ndarray, start: int, end: int, step: float) -> float:
    return float(times[end - 1] - times[start] + step)


def mmss(seconds: float) -> str:
    minutes, rest = divmod(max(seconds, 0.0), 60.0)
    return f"{int(minutes):02d}:{rest:04.1f}"


def pick_spread(indices: list[int], count: int) -> list[int]:
    """До count индексов, равномерно распределённых по списку (первый всегда включён)."""
    if len(indices) <= count:
        return list(indices)
    positions = np.linspace(0, len(indices) - 1, count).round().astype(int)
    return [indices[p] for p in dict.fromkeys(positions)]
