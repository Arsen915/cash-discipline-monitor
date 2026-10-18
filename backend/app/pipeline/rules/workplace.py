"""Правила про рабочее место кассира: уход во время обслуживания и ценности без присмотра."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..geometry import box_intersection_area, polygon_bbox
from ..quality import THUMB_WIDTH
from .base import Event, EvidenceRef, Rule, RuleContext, fill_gaps, mmss, run_duration, runs
from .catalog import CASH_UNATTENDED, WORKPLACE_ABANDONED


@dataclass
class Absence:
    start: int
    end: int              # не включительно
    duration: float
    client_at_departure: bool
    client_share: float
    returned: bool


def find_absences(ctx: RuleContext, min_sec: float) -> list[Absence]:
    if ctx.layout is None or not ctx.records:
        return []
    cfg = ctx.config
    times = ctx.times
    valid = ctx.valid
    present = np.array([s.cashier_present for s in ctx.states], dtype=bool)
    client = np.array([s.client_present for s in ctx.states], dtype=bool)
    # Непригодные кадры (перекрытая камера) не считаем отсутствием — это «неизвестно»
    present_smooth = fill_gaps(present | ~valid, times, cfg.presence_gap_fill_sec)
    client_smooth = fill_gaps(client, times, cfg.client_gap_fill_sec)

    result: list[Absence] = []
    for start, end in runs(~present_smooth):
        duration = run_duration(times, start, end, ctx.step_sec)
        if duration < min_sec:
            continue
        # Кассир должен был быть на месте до этого — иначе это не «уход», а пустая касса
        if not present[:start].any():
            continue
        window = np.abs(times - times[start]) <= 1.0
        result.append(Absence(
            start=start,
            end=end,
            duration=duration,
            client_at_departure=bool(client_smooth[window].any()),
            client_share=float(client_smooth[start:end].mean()),
            returned=end < len(times),
        ))
    return result


def _cashier_highlights(ctx: RuleContext, index: int, label: str) -> list:
    record, state = ctx.records[index], ctx.states[index]
    return [(record.persons[j].box, label) for j in state.cashier_side]


def _client_highlights(ctx: RuleContext, index: int) -> list:
    record, state = ctx.records[index], ctx.states[index]
    return [(record.persons[j].box, "CLIENT") for j in state.client_side
            if ctx.layout and ctx.layout.in_client_counter(record.persons[j].center)]


class WorkplaceAbandonedRule(Rule):
    vtype = WORKPLACE_ABANDONED

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        cfg = ctx.config
        times = ctx.times
        events: list[Event] = []
        for absence in find_absences(ctx, cfg.abandon_min_sec):
            if not (absence.client_at_departure or absence.client_share >= cfg.abandon_client_share):
                continue
            start_t = float(times[absence.start])
            end_t = float(times[absence.end - 1] + ctx.step_sec) if absence.returned else ctx.duration_sec
            excess = (absence.duration - cfg.abandon_min_sec) / (2 * cfg.abandon_min_sec)
            confidence = min(0.95, 0.6 + 0.25 * min(1.0, excess) + 0.1 * absence.client_at_departure)

            middle = (absence.start + absence.end - 1) // 2
            evidence = [EvidenceRef(absence.start, _client_highlights(ctx, absence.start))]
            if middle != absence.start:
                evidence.append(EvidenceRef(middle, _client_highlights(ctx, middle)))
            if absence.start > 0:
                evidence.append(EvidenceRef(absence.start - 1,
                                            _cashier_highlights(ctx, absence.start - 1, "CASHIER")))

            until = f"до {mmss(end_t)}" if absence.returned else "до конца записи"
            description = (
                f"В {mmss(start_t)} рабочее место кассира опустело: кассир ушёл из зоны кассы, "
                f"когда у стойки находился клиент. Рабочее место пустовало {absence.duration:.0f} с "
                f"({until}); клиент оставался у стойки {absence.client_share:.0%} этого времени, "
                f"что указывает на незавершённое обслуживание. На кадрах: момент ухода, пустое "
                f"рабочее место при клиенте у стойки и кассир на месте непосредственно перед уходом."
            )
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events


class CashUnattendedRule(Rule):
    vtype = CASH_UNATTENDED

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        cfg = ctx.config
        layout = ctx.layout
        if layout is None or layout.desk is None:
            return []
        times = ctx.times
        scale = THUMB_WIDTH / float(layout.width)
        thumb_shape = ctx.records[0].thumb.shape
        mask = np.zeros(thumb_shape, dtype=np.uint8)
        cv2.fillPoly(mask, [np.round(layout.desk * scale).astype(np.int32)], 1)
        mask = mask.astype(bool)
        if mask.sum() < 50:
            return []
        desk_box = polygon_bbox(layout.desk)
        desk_area = max((desk_box[2] - desk_box[0]) * (desk_box[3] - desk_box[1]), 1.0)

        def occupied(i: int) -> bool:
            return any(box_intersection_area(p.box, desk_box) > 0.15 * desk_area
                       for p in ctx.records[i].persons)

        def desk_pixels(i: int) -> np.ndarray:
            return cv2.GaussianBlur(ctx.records[i].thumb, (5, 5), 0).astype(np.float32)

        def edge_energy(image: np.ndarray) -> float:
            gx = cv2.Sobel(image, cv2.CV_32F, 1, 0)
            gy = cv2.Sobel(image, cv2.CV_32F, 0, 1)
            return float(np.abs(gx)[mask].mean() + np.abs(gy)[mask].mean())

        free = [i for i, s in enumerate(ctx.states) if s.valid and not occupied(i)]
        events: list[Event] = []
        for absence in find_absences(ctx, cfg.unattended_min_sec):
            if absence.client_at_departure or absence.client_share >= cfg.abandon_client_share:
                continue  # это WORKPLACE_ABANDONED
            t0, t1 = times[absence.start] - 1.0, times[absence.end - 1] + 1.0
            reference_ids = [i for i in free if not (t0 <= times[i] <= t1)]
            inside_ids = [i for i in free if absence.start <= i < absence.end]
            if len(reference_ids) < 3 or not inside_ids:
                continue  # нет кадра «чистого» стола — честно не делаем вывод

            # Эталон: самые «пустые» (наименее текстурные) кадры стола без людей
            energies = np.array([edge_energy(desk_pixels(i)) for i in reference_ids])
            calmest = [reference_ids[k] for k in np.argsort(energies)[:max(3, len(reference_ids) // 3)]]
            reference = np.median(np.stack([desk_pixels(i) for i in calmest]), axis=0)
            current = np.median(np.stack([desk_pixels(i) for i in inside_ids]), axis=0)

            changed = (np.abs(current - reference) > 25.0) & mask
            changed_fraction = float(changed.sum() / mask.sum())
            added_objects = edge_energy(current) > 1.1 * edge_energy(reference)
            if changed_fraction < cfg.desk_change_min_fraction or not added_objects:
                continue

            start_t = float(times[absence.start])
            end_t = float(times[absence.end - 1] + ctx.step_sec) if absence.returned else ctx.duration_sec
            confidence = min(0.9, 0.5 + 2.0 * changed_fraction)
            desk_highlight = [(desk_box, "DESK")]
            middle = inside_ids[len(inside_ids) // 2]
            evidence = [EvidenceRef(absence.start, desk_highlight)]
            if middle != absence.start:
                evidence.append(EvidenceRef(middle, desk_highlight))
            if absence.start > 0:
                evidence.append(EvidenceRef(absence.start - 1,
                                            _cashier_highlights(ctx, absence.start - 1, "CASHIER")))
            until = f"до {mmss(end_t)}" if absence.returned else "до конца записи"
            description = (
                f"В {mmss(start_t)} кассир покинул рабочее место и отсутствовал "
                f"{absence.duration:.0f} с ({until}). Всё это время на рабочем столе оставались "
                f"предметы, которых нет в контрольном кадре пустого стола (изменено "
                f"{changed_fraction:.0%} площади стола). Проверьте по кадрам, являются ли они "
                f"наличными или другими ценностями."
            )
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events
