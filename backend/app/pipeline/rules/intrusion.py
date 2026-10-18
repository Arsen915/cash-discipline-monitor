"""Посторонние в зоне кассира: переход из клиентской зоны за стойку и «толпа» за стойкой."""

from __future__ import annotations

import numpy as np

from .base import Event, EvidenceRef, Rule, RuleContext, fill_gaps, mmss, run_duration, runs
from .catalog import UNAUTHORIZED_PERSON


class UnauthorizedPersonRule(Rule):
    vtype = UNAUTHORIZED_PERSON

    def evaluate(self, ctx: RuleContext) -> list[Event]:
        if ctx.layout is None:
            return []
        return self._crossings(ctx) + self._crowding(ctx)

    def _crossings(self, ctx: RuleContext) -> list[Event]:
        cfg = ctx.config
        times = ctx.times
        # track_id -> [(record_index, person_index, за стойкой?)]
        tracks: dict[int, list[tuple[int, int, bool]]] = {}
        for i, (record, state) in enumerate(zip(ctx.records, ctx.states)):
            if not state.valid:
                continue
            cashier_side = set(state.cashier_side)
            for j, person in enumerate(record.persons):
                tracks.setdefault(person.track_id, []).append((i, j, j in cashier_side))

        events: list[Event] = []
        for observations in tracks.values():
            obs_times = np.array([times[i] for i, _, _ in observations])
            behind = np.array([flag for _, _, flag in observations], dtype=bool)
            behind = fill_gaps(behind, obs_times, 0.5)
            for start, end in runs(behind):
                duration = run_duration(obs_times, start, end, ctx.step_sec)
                if duration < cfg.intrusion_min_sec or start == 0:
                    continue
                public_before = [k for k in range(start) if not behind[k]]
                public_span = (obs_times[public_before[-1]] - obs_times[public_before[0]] + ctx.step_sec
                               if public_before else 0.0)
                if public_span < cfg.intrusion_client_side_min_sec:
                    continue

                run_records = [observations[k][0] for k in range(start, end)]
                with_others = any(len(ctx.states[i].cashier_side) >= 2 for i in run_records)
                confidence = 0.8 if with_others else 0.6
                first_i, first_j, _ = observations[start]
                mid_i, mid_j, _ = observations[(start + end - 1) // 2]
                prev_i, prev_j, _ = observations[public_before[-1]]
                evidence = [EvidenceRef(first_i, [(ctx.records[first_i].persons[first_j].box, "INTRUDER")])]
                if mid_i != first_i:
                    evidence.append(EvidenceRef(mid_i, [(ctx.records[mid_i].persons[mid_j].box, "INTRUDER")]))
                evidence.append(EvidenceRef(prev_i, [(ctx.records[prev_i].persons[prev_j].box, "BEFORE")]))

                start_t = float(times[first_i])
                end_t = float(obs_times[end - 1] + ctx.step_sec)
                company = (" В это время за стойкой находился и кассир." if with_others
                           else " Других людей за стойкой в этот момент не было.")
                description = (
                    f"В {mmss(start_t)} человек, который до этого {public_span:.0f} с находился в "
                    f"клиентской зоне, перешёл за стойку в зону кассира и оставался там "
                    f"{duration:.0f} с (до {mmss(end_t)}).{company} Доступ в кассу предусмотрен "
                    f"только через отдельный закрывающийся вход, не из клиентского зала."
                )
                events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events

    def _crowding(self, ctx: RuleContext) -> list[Event]:
        cfg = ctx.config
        if not cfg.crowd_enabled:
            return []
        times = ctx.times
        counts = np.array([len(s.cashier_side) if s.valid else 0 for s in ctx.states])
        crowded = fill_gaps(counts >= 2, times, 1.0)
        events: list[Event] = []
        for start, end in runs(crowded):
            duration = run_duration(times, start, end, ctx.step_sec)
            if duration < cfg.crowd_min_sec:
                continue
            peak = int(counts[start:end].max())
            indices = [i for i in range(start, end) if counts[i] >= 2]
            if not indices:
                continue
            chosen = [indices[0]]
            if indices[len(indices) // 2] != indices[0]:
                chosen.append(indices[len(indices) // 2])
            evidence = [
                EvidenceRef(i, [(ctx.records[i].persons[j].box, "STAFF?") for j in ctx.states[i].cashier_side])
                for i in chosen
            ]
            start_t = float(times[indices[0]])
            end_t = float(times[end - 1] + ctx.step_sec)
            excess = (duration - cfg.crowd_min_sec) / cfg.crowd_min_sec
            confidence = min(0.85, 0.55 + 0.3 * min(1.0, excess))
            description = (
                f"С {mmss(start_t)} по {mmss(end_t)} ({duration:.0f} с) за стойкой в зоне кассира "
                f"одновременно находились {peak} человека. В кассу допускаются только "
                f"уполномоченные работники; проверьте по кадрам, является ли второй человек "
                f"кассовым или контролирующим работником."
            )
            events.append(Event(self.vtype, start_t, end_t, start_t, confidence, description, evidence))
        return events
