"""Пороговые параметры правил. Значения по умолчанию можно переопределить JSON-файлом (RULES_FILE).

Пороги подбираются на размеченном датасете утилитой tools/evaluate.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from pathlib import Path


@dataclass(frozen=True)
class RuleConfig:
    # --- детектор ---
    person_conf: float = 0.30
    phone_conf: float = 0.30
    bag_conf: float = 0.35
    phone_labels: tuple[str, ...] = ("cell phone",)
    bag_labels: tuple[str, ...] = ("handbag", "backpack", "suitcase")

    # --- зоны (в единицах «масштаба человека» — медианной диагонали бокса) ---
    workplace_radius: float = 1.4
    client_radius: float = 1.8

    # --- камера ---
    obstruction_min_sec: float = 1.5
    obstruction_cell_fraction: float = 0.5

    # --- рабочее место кассира ---
    abandon_min_sec: float = 3.0
    presence_gap_fill_sec: float = 0.75
    client_gap_fill_sec: float = 1.5
    abandon_client_share: float = 0.6
    unattended_min_sec: float = 6.0
    desk_change_min_fraction: float = 0.08

    # --- посторонние в зоне кассира ---
    intrusion_min_sec: float = 2.0
    intrusion_client_side_min_sec: float = 1.0
    crowd_enabled: bool = True
    crowd_min_sec: float = 8.0

    # --- предметы ---
    phone_min_hits: int = 3
    phone_gap_fill_sec: float = 2.0
    phone_min_peak_conf: float = 0.40
    bag_min_sec: float = 6.0
    bag_min_fraction: float = 0.4

    # --- итог ---
    min_confidence: float = 0.5
    max_events_per_type: int = 5
    merge_gap_sec: float = 3.0

    @property
    def detector_labels(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(("person", *self.phone_labels, *self.bag_labels)))

    @property
    def detector_min_conf(self) -> float:
        return min(self.person_conf, self.phone_conf, self.bag_conf)


def load_rule_config(path: Path | None) -> RuleConfig:
    config = RuleConfig()
    if path is None:
        return config
    overrides = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name: f for f in fields(RuleConfig)}
    unknown = sorted(set(overrides) - set(known))
    if unknown:
        raise ValueError(f"Неизвестные параметры в {path}: {unknown}")
    converted = {}
    for name, value in overrides.items():
        default = getattr(config, name)
        converted[name] = tuple(value) if isinstance(default, tuple) else type(default)(value)
    return replace(config, **converted)
