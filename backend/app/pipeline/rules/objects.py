"""Запрещённые предметы в зоне кассира: мобильный телефон и личные сумки."""

from __future__ import annotations

import numpy as np

from .base import Event, EvidenceRef, Rule, RuleContext, fill_gaps, mmss, run_duration, runs
from .catalog import MOBILE_PHONE, PERSONAL_BELONGINGS


def _hits(ctx: RuleContext, attribute: str) -> tuple[np.ndarray, np.ndarray]:
    """Маска кадров с объектом и максимальная уверенность детектора по кадру."""
    mask = np.zeros(len(ctx.records), dtype=bool)
    peak = np.zeros(len(ctx.records))
    for i, (record, state) in enumerate(zip(ctx.records, ctx.states)):
        indices = getattr(state, attribute)
        if state.valid and indices:
            mask[i] = True
            peak[i] = max(record.objects[j].confidence for j in indices)
    return mask, peak


def _highlights(ctx: RuleContext, index: int, attribute: str, label: str) -> list:
    record = ctx.records[index]
    return [(record.objects[j].box, label) for j in getattr(ctx.states[index], attribute)]


class MobilePhoneRule(Rule):
    vtype = MOBILE_PHONE

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        if ctx.layout is None:
            return []
        cfg = ctx.config
        times = ctx.times
        mask, peak = _hits(ctx, "phones")
        events: list[Event] = []
        for start, end in runs(fill_gaps(mask, times, cfg.phone_gap_fill_sec)):
            hit_ids = [i for i in range(start, end) if mask[i]]
            best = float(peak[start:end].max())
            if len(hit_ids) < cfg.phone_min_hits or best < cfg.phone_min_peak_conf:
                continue
            first = hit_ids[0]
            strongest = sorted(hit_ids[1:], key=lambda i: -peak[i])[:2]
            evidence = [EvidenceRef(i, _highlights(ctx, i, "phones", "PHONE"))
                        for i in [first, *sorted(strongest)]]
            start_t = float(times[first])
            end_t = float(times[hit_ids[-1]] + ctx.step_sec)
            duration = run_duration(times, start, end, ctx.step_sec)
            confidence = min(0.95, 0.45 + 0.5 * best + 0.05 * (len(hit_ids) >= 5))
            description = (
                f"С {mmss(start_t)} в зоне кассира за стойкой виден мобильный телефон: обнаружен "
                f"на {len(hit_ids)} кадрах в течение {duration:.0f} с (до {mmss(end_t)}), "
                f"максимальная уверенность детектора {best:.2f}. В кассовый узел разрешено вносить "
                f"только средства связи без функции фото- и видеофиксации; наличие камеры у "
                f"устройства подтвердите по кадру."
            )
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events


class PersonalBelongingsRule(Rule):
    vtype = PERSONAL_BELONGINGS

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        if ctx.layout is None:
            return []
        cfg = ctx.config
        times = ctx.times
        mask, peak = _hits(ctx, "bags")
        events: list[Event] = []
        for start, end in runs(fill_gaps(mask, times, 2.0)):
            duration = run_duration(times, start, end, ctx.step_sec)
            hit_ids = [i for i in range(start, end) if mask[i]]
            if duration < cfg.bag_min_sec or len(hit_ids) / (end - start) < cfg.bag_min_fraction:
                continue
            first = hit_ids[0]
            evidence = [EvidenceRef(i, _highlights(ctx, i, "bags", "BAG"))
                        for i in dict.fromkeys([first, hit_ids[len(hit_ids) // 2], hit_ids[-1]])]
            start_t = float(times[first])
            end_t = float(times[hit_ids[-1]] + ctx.step_sec)
            mean_conf = float(np.mean(peak[hit_ids]))
            confidence = min(0.9, 0.5 + 0.4 * mean_conf)
            description = (
                f"С {mmss(start_t)} по {mmss(end_t)} ({duration:.0f} с) за стойкой на рабочем месте "
                f"кассира находится сумка/рюкзак (средняя уверенность детектора {mean_conf:.2f}). "
                f"Личные вещи работников должны храниться вне кассового узла; убедитесь по кадру, "
                f"что это не инкассаторская сумка, принятая по препроводительному документу."
            )
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events
