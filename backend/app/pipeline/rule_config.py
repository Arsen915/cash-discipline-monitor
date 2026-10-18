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
    phone_in_hand_conf: float = 0.22      # телефон в руке кассира: допускаем меньшую уверенность
    bag_conf: float = 0.30
    equipment_conf: float = 0.30
    phone_labels: tuple[str, ...] = ("cell phone",)
    bag_labels: tuple[str, ...] = ("handbag", "backpack", "suitcase")
    # Оборудование кассы: принтер детектор часто называет «suitcase», а заодно «microwave»/«tv»;
    # совпадающие с ним «сумки» и «телефоны» отбрасываются
    equipment_labels: tuple[str, ...] = ("tv", "laptop", "keyboard", "microwave", "oven", "toaster")

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
    shift_absence_min_sec: float = 30.0   # отлучка без клиента у стойки (уход во время смены)
    desk_change_min_fraction: float = 0.08

    # --- посторонние в зоне кассира ---
    intrusion_min_sec: float = 2.0
    intrusion_client_side_min_sec: float = 1.0
    crowd_enabled: bool = True
    crowd_min_sec: float = 8.0

    # --- предметы ---
    phone_min_hits: int = 3
    phone_min_hits_in_hand: int = 2
    phone_gap_fill_sec: float = 2.0
    phone_min_peak_conf: float = 0.40
    phone_min_peak_conf_in_hand: float = 0.32
    bag_min_sec: float = 4.0
    bag_min_fraction: float = 0.35
    bag_gap_fill_sec: float = 3.0

    # --- неподвижное оборудование (принтер, терминал), похожее на сумку/телефон ---
    fixture_min_coverage: float = 0.6     # доля пригодных кадров, на которых объект виден
    fixture_max_shift: float = 0.25       # смещение центра относительно диагонали бокса
    fixture_keep_bag_conf: float = 0.6    # уверенную неподвижную сумку/рюкзак всё же считаем сумкой
    fixture_keep_phone_conf: float = 0.7
    fixture_min_frames: int = 15

    # --- итог ---
    min_confidence: float = 0.5
    max_events_per_type: int = 5
    merge_gap_sec: float = 3.0

    @property
    def detector_labels(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(("person", *self.phone_labels, *self.bag_labels, *self.equipment_labels)))

    @property
    def detector_min_conf(self) -> float:
        return min(self.person_conf, self.phone_conf, self.phone_in_hand_conf, self.bag_conf, self.equipment_conf)


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
