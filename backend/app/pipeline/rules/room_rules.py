"""Правила на модели помещения (room.py): работают при любом ракурсе камеры."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..geometry import box_iou
from ..room import Room, changed_fraction, foot, masked_median, to_thumb_box
from .base import Event, EvidenceRef, Rule, RuleContext, fill_gaps, mmss, run_duration, runs
from .catalog import (
    DOOR_LEFT_OPEN,
    MOBILE_PHONE,
    PERSONAL_BELONGINGS,
    STORAGE_LEFT_OPEN,
    UNAUTHORIZED_PERSON,
    WORKPLACE_LEFT_UNSECURED,
)


def _ok_persons(ctx: RuleContext, i: int):
    room: Room = ctx.room
    record = ctx.records[i]
    return [p for p, good in zip(record.persons, room.person_ok[i]) if good]


def _indices(times: np.ndarray, start: float, end: float, valid: np.ndarray | None = None) -> list[int]:
    return [i for i, t in enumerate(times) if start <= t <= end and (valid is None or valid[i])]


# ------------------------------------------------------------------ уход с рабочего места
class WorkplaceLeftRule(Rule):
    """Кассир ушёл из помещения, оставив рабочее место необеспеченным.

    Нарушение, если в момент ухода у стола был клиент, или если экран компьютера после
    ухода выглядит так же, как во время работы (не заблокирован).
    """

    vtype = WORKPLACE_LEFT_UNSECURED
    uses_room = True

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        room = ctx.room
        if room is None:
            return []
        cfg = ctx.config
        times = ctx.times
        valid = ctx.valid
        n = len(times)
        people = [_ok_persons(ctx, i) for i in range(n)]
        counts = np.array([len(p) for p in people])
        # Расстояние от ног ближайшего человека до рабочего места кассира, в ростах кассира
        dist = np.array([min((float(np.linalg.norm(foot(p.box) - room.anchor)) / room.height for p in ps),
                             default=np.inf) for ps in people])
        near = dist <= cfg.leave_near_dist
        laptop = self._laptop_box(ctx)

        events: list[Event] = []
        absent = fill_gaps(~near & valid, times, 0.5)
        for start, end in runs(absent):
            # Уходить можно только с места, где кассир уже работал (а не пройдя мимо при входе)
            if near[:start].sum() * ctx.step_sec < cfg.leave_min_presence_sec:
                continue
            before = int(counts[max(0, start - 3):start].max())
            # Ушёл из помещения: людей стало меньше, чем было до ухода, и трек кассира пропал
            gone = [i for i in range(start, end) if counts[i] < before and valid[i]
                    and not any(p.track_id in room.cashier_tracks for p in people[i])]
            if not gone:
                continue
            gone_span = float(times[gone[-1]] - times[gone[0]] + ctx.step_sec)
            till_end = end == n
            if gone_span < (cfg.leave_end_min_sec if till_end else cfg.leave_gone_sec):
                continue
            client_present = before >= 2 and counts[gone].min() >= 1
            t_gone = float(times[gone[0]])
            # Момент ухода — когда кассир отошёл от кресла (а не когда скрылся за дверью)
            window = [i for i in range(start) if t_gone - cfg.leave_lookback_sec <= times[i] < t_gone]
            away = [i for i in window if dist[i] > cfg.leave_away_dist]
            leave_index = away[0] if away else start
            start_t = float(times[leave_index])

            # Экран: сравниваем вид во время работы (начало записи) и после ухода
            screen_state = "unknown"
            if laptop is not None:
                pre = [i for i in _indices(times, 0.0, cfg.screen_window_sec, valid) if near[i]]
                post = [i for i in gone if times[i] >= t_gone + 0.3]
                box_t = to_thumb_box(laptop, room.thumb_scale(), ctx.records[0].thumb.shape, 0.05, 0.05)
                a, _ = masked_median(ctx.records, room, pre, box_t, 0.3)
                b, _ = masked_median(ctx.records, room, post, box_t, 0.3)
                if a is not None and b is not None:
                    screen_state = "locked" if changed_fraction(a, b) >= cfg.screen_change_min else "unlocked"

            if client_present:
                confidence, reason = 0.85, "в помещении в этот момент оставался клиент — обслуживание не завершено"
            elif screen_state == "unlocked":
                confidence = 0.75
                reason = ("экран компьютера после ухода остался таким же, как во время работы — "
                          "компьютер не заблокирован, рабочее место не обеспечено")
            elif screen_state == "unknown" and cfg.leave_flag_unverified:
                confidence = 0.6
                reason = "по записи не видно, что кассир заблокировал компьютер и убрал ценности перед уходом"
            else:
                continue

            returned = not till_end
            end_t = float(times[end - 1] + ctx.step_sec) if returned else ctx.duration_sec
            evidence = [EvidenceRef(leave_index, [(p.box, "CASHIER") for p in people[leave_index]])]
            middle = gone[len(gone) // 2]
            evidence.append(EvidenceRef(middle, [(laptop, "SCREEN")] if laptop else []))
            if leave_index > 0:
                evidence.append(EvidenceRef(leave_index - 1, [(p.box, "CASHIER") for p in people[leave_index - 1]]))
            until = f"вернулся в {mmss(end_t)}" if returned else "не вернулся до конца записи"
            description = (f"В {mmss(start_t)} кассир встал с рабочего места и вышел из помещения "
                           f"({until}); {reason}.")
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events

    @staticmethod
    def _laptop_box(ctx: RuleContext):
        boxes = [o.box for r in ctx.records for o in r.objects
                 if o.label in ctx.config.screen_labels and o.confidence >= 0.5]
        if len(boxes) < 3:
            return None
        return tuple(float(v) for v in np.median(np.array(boxes), axis=0))


# ------------------------------------------------------------ оставлено открытым (сейф/дверь)
@dataclass
class _Spot:
    start: float
    end: float
    box: tuple
    door: bool
    first_index: int
    last_index: int


class LeftOpenRule(Rule):
    """Место взаимодействия (сейф, шкаф, дверь) после ухода человека выглядит иначе, чем до."""

    vtype = STORAGE_LEFT_OPEN
    uses_room = True

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        room = ctx.room
        if room is None:
            return []
        cfg = ctx.config
        times = ctx.times
        shape = ctx.records[0].thumb.shape
        events: list[Event] = []
        for spot in self._spots(ctx):
            box_t = to_thumb_box(spot.box, room.thumb_scale(), shape, cfg.spot_expand_x, 0.05)
            before_ids = _indices(times, spot.start - cfg.spot_window_sec, spot.start - 0.3, ctx.valid)
            after_ids = _indices(times, spot.end + cfg.spot_settle_sec, spot.end + cfg.spot_window_sec, ctx.valid)
            before, _ = masked_median(ctx.records, room, before_ids, box_t)
            after, _ = masked_median(ctx.records, room, after_ids, box_t)
            if before is None or after is None:
                continue
            fraction = changed_fraction(before, after)
            if fraction < cfg.spot_change_min:
                continue
            vtype = DOOR_LEFT_OPEN if spot.door else STORAGE_LEFT_OPEN
            what = "дверь в помещение кассы" if spot.door else "место хранения (сейф/шкаф), с которым работал кассир"
            confidence = min(0.9, 0.55 + 1.5 * fraction)
            evidence = [EvidenceRef(spot.last_index, [(spot.box, "LEFT OPEN?")])]
            if after_ids:
                evidence.append(EvidenceRef(after_ids[len(after_ids) // 2], [(spot.box, "AFTER")]))
            if before_ids:
                evidence.append(EvidenceRef(before_ids[-1], [(spot.box, "BEFORE")]))
            description = (f"В {mmss(spot.end)} человек отошёл, оставив {what} в изменённом состоянии: "
                           f"вид этого места после ухода отличается от вида до взаимодействия "
                           f"({fraction:.0%} площади). Вероятно, дверца/дверь оставлена открытой — "
                           f"сравните кадры «до» и «после».")
            events.append(Event(vtype, spot.end, spot.end + cfg.spot_window_sec, spot.end, confidence,
                                description, evidence))
        return events

    def _spots(self, ctx: RuleContext) -> list[_Spot]:
        room = ctx.room
        cfg = ctx.config
        width, height = room.frame_size
        border = 0.03 * max(width, height)
        tracks: dict[int, list[tuple[int, object]]] = {}
        for i, record in enumerate(ctx.records):
            if not ctx.states[i].valid:
                continue
            for person, good in zip(record.persons, room.person_ok[i]):
                if good:
                    tracks.setdefault(person.track_id, []).append((i, person))
        spots: list[_Spot] = []
        times = ctx.times
        for observations in tracks.values():
            if len(observations) < 2:
                continue
            # Пересечение двери: трек появился или исчез не у края кадра и не на рабочем месте
            for index, person, appeared in ((observations[0][0], observations[0][1], True),
                                            (observations[-1][0], observations[-1][1], False)):
                x1, y1, x2, y2 = person.box
                at_edge = x1 < border or y1 < border or x2 > width - border or y2 > height - border
                if at_edge or room.at_workplace(person.box, cfg.room_workplace_radius * 1.3):
                    continue
                if appeared and times[index] < 1.0:
                    continue
                t = float(times[index])
                spots.append(_Spot(t - 0.5, t + 0.5, person.box, True, index, index))
            # Остановки вне рабочего места у кассира (трек хоть раз был на рабочем месте)
            if not any(room.at_workplace(p.box, cfg.room_workplace_radius) for _, p in observations):
                continue
            group: list[tuple[int, object]] = []
            for item in observations + [(None, None)]:
                index, person = item
                if group and (person is None or np.linalg.norm(foot(person.box) - foot(group[0][1].box))
                              > 0.3 * room.height):
                    first, last = group[0][0], group[-1][0]
                    span = times[last] - times[first] + ctx.step_sec
                    box = group[len(group) // 2][1].box
                    if span >= cfg.spot_min_sec and not room.at_workplace(box, cfg.room_workplace_radius * 1.3):
                        spots.append(_Spot(float(times[first]), float(times[last]), box, False, first, last))
                    group = []
                if person is not None:
                    group.append((index, person))
        return spots


# ----------------------------------------------------------------------- телефон у кассира
class CashierPhoneRule(Rule):
    vtype = MOBILE_PHONE
    uses_room = True

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        room = ctx.room
        if room is None:
            return []
        cfg = ctx.config
        times = ctx.times
        hits = np.zeros(len(times), bool)
        best = np.zeros(len(times))
        boxes: dict[int, list] = {}
        for i, record in enumerate(ctx.records):
            if not ctx.states[i].valid:
                continue
            people = _ok_persons(ctx, i)
            for obj in record.objects:
                if obj.label not in cfg.phone_labels or obj.confidence < cfg.phone_conf:
                    continue
                cx, cy = (obj.box[0] + obj.box[2]) / 2, (obj.box[1] + obj.box[3]) / 2
                holder = next((p for p in people if self._inside(p.box, cx, cy, 0.15)), None)
                if holder is None or not self._is_cashier(ctx, holder):
                    continue
                # Телефон в руке крупнее пачки купюр/калькулятора на столе, которые COCO-детектор
                # тоже называет «cell phone»: требуем размер не меньше доли роста держащего
                size = float(np.sqrt(max((obj.box[2] - obj.box[0]) * (obj.box[3] - obj.box[1]), 0.0)))
                if size < cfg.phone_min_rel_size * (holder.box[3] - holder.box[1]):
                    continue
                hits[i] = True
                best[i] = max(best[i], obj.confidence)
                boxes.setdefault(i, []).append((obj.box, "PHONE"))
        events: list[Event] = []
        for start, end in runs(fill_gaps(hits, times, cfg.phone_gap_fill_sec)):
            hit_ids = [i for i in range(start, end) if hits[i]]
            peak = float(best[start:end].max())
            if len(hit_ids) < cfg.phone_min_hits or peak < cfg.phone_room_min_peak_conf:
                continue
            first = hit_ids[0]
            strongest = sorted(hit_ids[1:], key=lambda i: -best[i])[:2]
            evidence = [EvidenceRef(i, boxes[i]) for i in [first, *sorted(strongest)]]
            start_t, end_t = float(times[first]), float(times[hit_ids[-1]] + ctx.step_sec)
            confidence = min(0.95, 0.45 + 0.5 * peak + 0.05 * (len(hit_ids) >= 5))
            description = (f"С {mmss(start_t)} у кассира в руках мобильный телефон: виден на {len(hit_ids)} "
                           f"кадрах до {mmss(end_t)}, максимальная уверенность детектора {peak:.2f}. "
                           f"В кассовое помещение разрешено вносить только средства связи без функции фото- и "
                           f"видеофиксации; наличие камеры у устройства подтвердите по кадру.")
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events

    @staticmethod
    def _inside(box, x: float, y: float, pad: float) -> bool:
        w, h = box[2] - box[0], box[3] - box[1]
        return box[0] - pad * w <= x <= box[2] + pad * w and box[1] - pad * h <= y <= box[3] + pad * h

    @staticmethod
    def _is_cashier(ctx: RuleContext, person) -> bool:
        room = ctx.room
        return person.track_id in room.cashier_tracks or room.at_workplace(person.box, ctx.config.room_workplace_radius)


# ------------------------------------------------------------------- новая сумка у кассира
class NewBagRule(Rule):
    """Сумка/рюкзак, появившиеся у рабочего места в ходе записи (оборудование, стоящее с начала, не в счёт)."""

    vtype = PERSONAL_BELONGINGS
    uses_room = True

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        room = ctx.room
        if room is None:
            return []
        cfg = ctx.config
        times = ctx.times
        clusters: list[dict] = []
        for i, record in enumerate(ctx.records):
            for obj in record.objects:
                if obj.label not in cfg.bag_labels or obj.confidence < cfg.bag_conf:
                    continue
                cluster = next((c for c in clusters if box_iou(c["box"], obj.box) > 0.3), None)
                if cluster is None:
                    clusters.append({"box": obj.box, "hits": [(i, obj.confidence)]})
                else:
                    cluster["hits"].append((i, obj.confidence))
        # Положение любых предметов в первые секунды — это «фон» (счётная машинка, принтер)
        initial = [o.box for i in _indices(times, 0, cfg.bag_static_sec) for o in ctx.records[i].objects]
        events: list[Event] = []
        for cluster in clusters:
            ids = [i for i, _ in cluster["hits"]]
            first_t = float(times[ids[0]])
            span = float(times[ids[-1]] - first_t + ctx.step_sec)
            if first_t <= cfg.bag_static_sec or any(box_iou(cluster["box"], b) > 0.3 for b in initial):
                continue
            if len(ids) < cfg.bag_min_hits or span < cfg.bag_min_sec:
                continue
            if np.linalg.norm(foot(cluster["box"]) - room.anchor) > cfg.bag_max_dist * room.height:
                continue
            mean_conf = float(np.mean([c for _, c in cluster["hits"]]))
            if mean_conf < cfg.bag_min_mean_conf:
                continue
            evidence = [EvidenceRef(i, [(cluster["box"], "BAG")]) for i in dict.fromkeys([ids[0], ids[len(ids) // 2]])]
            description = (f"С {mmss(first_t)} у рабочего места кассира появилась сумка/рюкзак и оставалась там "
                           f"{span:.0f} с (средняя уверенность детектора {mean_conf:.2f}). Личные вещи работников "
                           f"должны храниться вне кассового узла; убедитесь по кадру, что это не инкассаторская "
                           f"сумка, принятая по препроводительному документу.")
            events.append(Event(self.vtype, first_t, first_t + span, first_t, min(0.9, 0.5 + 0.4 * mean_conf),
                                description, evidence))
        return events


# ------------------------------------------------------------------------- третий человек
class ExtraPersonRule(Rule):
    """В помещении одновременно больше людей, чем кассир и один клиент."""

    vtype = UNAUTHORIZED_PERSON
    uses_room = True

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        room = ctx.room
        if room is None:
            return []
        cfg = ctx.config
        times = ctx.times
        counts = np.array([len(_ok_persons(ctx, i)) if ctx.states[i].valid else 0 for i in range(len(times))])
        crowded = fill_gaps(counts >= cfg.crowd_persons, times, 1.0)
        events: list[Event] = []
        for start, end in runs(crowded):
            duration = run_duration(times, start, end, ctx.step_sec)
            if duration < cfg.crowd_room_min_sec:
                continue
            ids = [i for i in range(start, end) if counts[i] >= cfg.crowd_persons]
            start_t, end_t = float(times[ids[0]]), float(times[end - 1] + ctx.step_sec)
            evidence = [EvidenceRef(i, [(p.box, "PERSON") for p in _ok_persons(ctx, i)])
                        for i in dict.fromkeys([ids[0], ids[len(ids) // 2]])]
            description = (f"С {mmss(start_t)} по {mmss(end_t)} ({duration:.0f} с) в помещении кассы одновременно "
                           f"находились {int(counts[start:end].max())} человека: помимо кассира и обслуживаемого "
                           f"клиента — посторонний. Доступ в кассу имеют только уполномоченные работники.")
            confidence = min(0.85, 0.55 + 0.1 * duration)
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events
