"""Перекрытие обзора камеры видеонаблюдения."""

from __future__ import annotations

from .base import Event, EvidenceRef, Rule, RuleContext, fill_gaps, mmss, run_duration, runs
from .catalog import CAMERA_OBSTRUCTION


class CameraObstructionRule(Rule):
    vtype = CAMERA_OBSTRUCTION

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        cfg = ctx.config
        times = ctx.times
        obstructed = fill_gaps(~ctx.valid, times, 0.5)
        events: list[Event] = []
        for start, end in runs(obstructed):
            duration = run_duration(times, start, end, ctx.step_sec)
            if duration < cfg.obstruction_min_sec:
                continue
            start_t = float(times[start])
            end_t = float(times[end - 1] + ctx.step_sec) if end < len(times) else ctx.duration_sec
            evidence = [EvidenceRef(start)]
            middle = (start + end - 1) // 2
            if middle != start:
                evidence.append(EvidenceRef(middle))
            if start > 0:
                evidence.append(EvidenceRef(start - 1))
            confidence = min(0.95, 0.7 + 0.25 * min(1.0, duration / 5.0))
            until = f"до {mmss(end_t)}" if end < len(times) else "до конца записи"
            description = (
                f"С {mmss(start_t)} обзор камеры над кассой перекрыт или изображение потеряно на "
                f"{duration:.1f} с ({until}): кадр стал однородным/тёмным либо большая часть "
                f"кадра закрыта, рабочее место кассира не просматривается. Последний кадр — "
                f"состояние непосредственно перед перекрытием."
            )
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events
