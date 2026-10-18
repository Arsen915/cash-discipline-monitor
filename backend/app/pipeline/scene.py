"""Перевод детекций кадра в состояние сцены относительно зон кассы."""

from __future__ import annotations

import numpy as np

from .geometry import box_area, box_intersection_area
from .records import FrameRecord, FrameState
from .rule_config import RuleConfig
from .zones import ZoneLayout


def build_states(records: list[FrameRecord], valid: np.ndarray, layout: ZoneLayout | None,
                 config: RuleConfig) -> list[FrameState]:
    states: list[FrameState] = []
    for record, is_valid in zip(records, valid):
        state = FrameState(valid=bool(is_valid))
        if layout is not None:
            for j, person in enumerate(record.persons):
                center = person.center
                if layout.in_cashier_side(center):
                    state.cashier_side.append(j)
                    if layout.in_workplace(center):
                        state.cashier_present = True
                else:
                    state.client_side.append(j)
                    if layout.in_client_counter(center):
                        state.client_present = True

            for j, obj in enumerate(record.objects):
                if not layout.in_cashier_side(obj.center):
                    continue
                if obj.label in config.phone_labels and obj.confidence >= config.phone_conf:
                    state.phones.append(j)
                elif obj.label in config.bag_labels and obj.confidence >= config.bag_conf:
                    # Сумку в руках клиента/инкассатора у стойки личной вещью кассира не считаем
                    area = max(box_area(obj.box), 1.0)
                    carried = any(
                        box_intersection_area(obj.box, record.persons[k].box) > 0.3 * area
                        for k in state.client_side
                    )
                    if not carried:
                        state.bags.append(j)
        states.append(state)
    return states
