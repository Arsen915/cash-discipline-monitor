"""Перевод детекций кадра в состояние сцены относительно зон кассы."""

from __future__ import annotations

import numpy as np

from .geometry import box_area, box_center, box_diag, box_intersection_area, box_iou
from .records import FrameRecord, FrameState
from .rule_config import RuleConfig
from .zones import ZoneLayout


def _overlaps_equipment(obj, equipment: list, min_iou: float) -> bool:
    return any(box_iou(obj.box, item.box) >= min_iou for item in equipment)


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

            equipment = [obj for obj in record.objects
                         if obj.label in config.equipment_labels and obj.confidence >= config.equipment_conf]
            for j, obj in enumerate(record.objects):
                if not layout.in_cashier_side(obj.center):
                    continue
                area = max(box_area(obj.box), 1.0)
                if obj.label in config.phone_labels:
                    # Телефон в руке: бокс пересекается с человеком за стойкой
                    in_hand = any(box_intersection_area(obj.box, record.persons[k].box) > 0.3 * area
                                  for k in state.cashier_side)
                    threshold = config.phone_in_hand_conf if in_hand else config.phone_conf
                    if obj.confidence < threshold or _overlaps_equipment(obj, equipment, 0.5):
                        continue
                    state.phones.append(j)
                    if in_hand:
                        state.phones_in_hand.append(j)
                elif obj.label in config.bag_labels and obj.confidence >= config.bag_conf:
                    if _overlaps_equipment(obj, equipment, 0.4):
                        continue  # принтер/монитор, принятый за сумку
                    # Сумку в руках клиента/инкассатора у стойки личной вещью кассира не считаем
                    carried = any(
                        box_intersection_area(obj.box, record.persons[k].box) > 0.3 * area
                        for k in state.client_side
                    )
                    if not carried:
                        state.bags.append(j)
        states.append(state)
    suppress_fixtures(records, states, config)
    return states


def suppress_fixtures(records: list[FrameRecord], states: list[FrameState], config: RuleConfig) -> None:
    """Убирает неподвижное оборудование, которое детектор принимает за сумку или телефон.

    Принтер, денежный терминал или монитор стоят на одном месте всю запись и никем не
    переносятся. Объект считается оборудованием, если он виден на большей части пригодных
    кадров, почти не смещается и детектор не уверен в нём (или называет его «suitcase» —
    типичная ошибка на принтерах). Уверенно распознанный рюкзак, пролежавший всю смену,
    по-прежнему остаётся нарушением.
    """
    valid_count = sum(1 for s in states if s.valid)
    if valid_count < config.fixture_min_frames:
        return
    for attribute, keep_conf in (("bags", config.fixture_keep_bag_conf),
                                 ("phones", config.fixture_keep_phone_conf)):
        clusters: list[dict] = []
        for i, (record, state) in enumerate(zip(records, states)):
            for j in getattr(state, attribute):
                obj = record.objects[j]
                cluster = next((c for c in clusters if box_iou(c["box"], obj.box) >= 0.5), None)
                if cluster is None:
                    cluster = {"box": obj.box, "hits": []}
                    clusters.append(cluster)
                cluster["hits"].append((i, j))

        for cluster in clusters:
            frames = {i for i, _ in cluster["hits"]}
            if len(frames) / valid_count < config.fixture_min_coverage:
                continue
            objects = [records[i].objects[j] for i, j in cluster["hits"]]
            centers = np.stack([box_center(o.box) for o in objects])
            diag = float(np.median([box_diag(o.box) for o in objects])) or 1.0
            shift = float(np.max(np.linalg.norm(centers - np.median(centers, axis=0), axis=1))) / diag
            if shift > config.fixture_max_shift:
                continue
            labels = [o.label for o in objects]
            mean_conf = float(np.mean([o.confidence for o in objects]))
            suitcase_like = labels.count("suitcase") > len(labels) / 2
            held = attribute == "phones" and sum(
                1 for i, j in cluster["hits"] if j in states[i].phones_in_hand) > 0.1 * len(cluster["hits"])
            if held or (mean_conf >= keep_conf and not suitcase_like):
                continue
            for i, j in cluster["hits"]:
                items = getattr(states[i], attribute)
                if j in items:
                    items.remove(j)
                if attribute == "phones" and j in states[i].phones_in_hand:
                    states[i].phones_in_hand.remove(j)
                states[i].fixtures.append(j)
