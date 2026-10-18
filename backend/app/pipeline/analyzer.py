"""Оркестрация анализа одного видео.

Проход 1: декодирование → выборка кадров → детекция → трекинг → метрики качества.
Проход 2 (по накопленным данным, без повторного чтения видео): перекрытие камеры →
калибровка зон → состояние сцены → правила → кадры-доказательства → JSON-ответ.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .detector import Detector
from .evidence import FrameCache, render_evidence
from .geometry import box_iou
from .quality import make_thumbnail, measure_quality, obstruction_mask
from .records import FrameRecord, ObjectObs, PersonObs
from .rule_config import RuleConfig
from .rules import Event, Rule, RuleContext, default_rules
from .scene import build_states
from .tracker import IoUTracker
from .video import FrameSampler, VideoError, probe_video
from .zones import ZoneLayout, calibrate_layout, person_scale

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]

MAX_SAMPLING_STEP_SEC = 1.5
MAX_EVIDENCE_FRAMES = 3


class VideoAnalyzer:
    def __init__(
        self,
        detector: Detector,
        config: RuleConfig,
        analysis_fps: float = 3.0,
        max_analyzed_frames: int = 450,
        budget_sec: float = 150.0,
        zones_file: Path | None = None,
        evidence_max_width: int = 960,
        evidence_quality: int = 82,
        evidence_annotate: bool = True,
        object_zoom: bool = True,
        rules: list[Rule] | None = None,
    ):
        self.detector = detector
        self.object_zoom = object_zoom
        self.config = config
        self.analysis_fps = analysis_fps
        self.max_analyzed_frames = max_analyzed_frames
        self.budget_sec = budget_sec
        self.zones_file = zones_file
        self.evidence_max_width = evidence_max_width
        self.evidence_quality = evidence_quality
        self.evidence_annotate = evidence_annotate
        self.rules = rules if rules is not None else default_rules()

    # ------------------------------------------------------------------ public
    def analyze(self, path: Path, progress: ProgressCallback | None = None,
                debug: bool = False) -> dict:
        report = progress or (lambda fraction, stage: None)
        started = time.monotonic()
        report(0.02, "Чтение метаданных видео")
        meta = probe_video(path)

        estimated_duration = meta.duration_sec if meta.duration_sec > 0 else 60.0
        step = max(1.0 / self.analysis_fps, estimated_duration / max(self.max_analyzed_frames, 1))
        sampler = FrameSampler(path, meta.fps, step)
        tracker = IoUTracker()
        cache = FrameCache(self.evidence_max_width)
        records: list[FrameRecord] = []
        cfg = self.config

        report(0.05, "Детекция людей и предметов")
        last_report = 0.0
        presence: dict[int, float] = {}
        last_tick, last_time = time.monotonic(), 0.0
        rate: float | None = None  # секунд обработки на секунду видео (EMA)
        cooldown = 0
        for sample in sampler:
            detections = self.detector.detect(sample.image)
            people = [d for d in detections if d.label == "person" and d.confidence >= cfg.person_conf]
            track_ids = tracker.update(sample.time_sec, [d.box for d in people])
            for track_id in track_ids:
                presence[track_id] = presence.get(track_id, 0.0) + sampler.step_sec
            persons = [PersonObs(tid, d.box, d.confidence) for tid, d in zip(track_ids, people)]
            objects = [ObjectObs(d.label, d.box, d.confidence) for d in detections if d.label != "person"]
            if self.object_zoom and persons:
                objects = self._zoom_objects(sample.image, persons, presence, objects)
            thumb = make_thumbnail(sample.image)
            cache.add(sample.image)
            records.append(FrameRecord(len(records), sample.frame_index, sample.time_sec, persons,
                                       objects, measure_quality(thumb), thumb))

            # Адаптация под бюджет: прогноз = прошло + остаток видео × текущая скорость.
            # Если не успеваем, разрежаем выборку кадров (после изменения — пауза в 3 кадра).
            now = time.monotonic()
            if sample.time_sec > last_time:
                current = (now - last_tick) / (sample.time_sec - last_time)
                rate = current if rate is None else 0.7 * rate + 0.3 * current
            last_tick, last_time = now, sample.time_sec
            cooldown = max(0, cooldown - 1)
            if rate is not None and cooldown == 0 and sampler.step_sec < MAX_SAMPLING_STEP_SEC:
                projected = (now - started) + max(estimated_duration - sample.time_sec, 0.0) * rate
                if projected > 0.85 * self.budget_sec:
                    new_step = min(sampler.step_sec * 1.5, MAX_SAMPLING_STEP_SEC)
                    rate *= sampler.step_sec / new_step
                    sampler.step_sec = new_step
                    cooldown = 3
                    logger.info("Шаг выборки увеличен до %.2f с (прогноз %.0f с)", new_step, projected)

            position = min(sample.time_sec / estimated_duration, 1.0)
            if position - last_report >= 0.02:
                last_report = position
                report(0.05 + 0.8 * position, "Детекция людей и предметов")

        if not records:
            raise VideoError("Не удалось декодировать ни одного кадра")

        duration = max(sampler.frames_decoded / sampler.fps, records[-1].time_sec)
        times = np.array([r.time_sec for r in records])
        actual_step = float(np.median(np.diff(times))) if len(times) > 1 else step
        width, height = records[0].thumb.shape[1], records[0].thumb.shape[0]
        frame_h, frame_w = meta.height, meta.width

        report(0.87, "Калибровка зон кассы")
        valid = ~obstruction_mask([r.quality for r in records], cfg.obstruction_cell_fraction)
        layout = self._layout(records, valid, frame_w, frame_h, duration, actual_step)
        states = build_states(records, valid, layout, cfg)
        ctx = RuleContext(records, states, layout, cfg, duration, actual_step)

        report(0.9, "Проверка правил")
        events: list[Event] = []
        for rule in self.rules:
            try:
                events.extend(rule.evaluate(ctx))
            except Exception:  # одно сломанное правило не должно ронять весь анализ
                logger.exception("Ошибка в правиле %s", type(rule).__name__)
        events = self._postprocess(events)
        accepted = [e for e in events if e.confidence >= cfg.min_confidence]

        report(0.95, "Подготовка кадров-доказательств")
        violations = [self._violation(event, ctx, cache) for event in accepted]
        result: dict = {
            "verdict": "violation" if violations else "no_violation",
            "violations": violations,
            "video": {
                "duration_sec": round(duration, 2),
                "fps": round(meta.fps, 3),
                "width": frame_w,
                "height": frame_h,
                "codec": meta.codec,
                "frames_total": sampler.frames_decoded,
                "frames_analyzed": len(records),
                "sampling_step_sec": round(actual_step, 3),
            },
            "analysis": {
                "detector": self.detector.name,
                "layout": layout.to_dict() if layout else None,
                "rules": [rule.vtype.code for rule in self.rules],
                "events_below_threshold": len(events) - len(accepted),
                "elapsed_sec": round(time.monotonic() - started, 2),
            },
        }
        if debug:
            result["debug"] = {
                "thumb_size": [width, height],
                "timeline": [self._timeline_row(r, s) for r, s in zip(records, states)],
                "rejected_events": [
                    {"code": e.vtype.code, "timecode_sec": round(e.timecode_sec, 2),
                     "confidence": round(e.confidence, 2)}
                    for e in events if e.confidence < cfg.min_confidence
                ],
            }
        report(1.0, "Готово")
        return result

    # ----------------------------------------------------------------- helpers
    def _zoom_objects(self, image: np.ndarray, persons: list[PersonObs], presence: dict[int, float],
                      objects: list[ObjectObs]) -> list[ObjectObs]:
        """Повторная детекция мелких предметов в увеличенном кропе вокруг кассира.

        Сверху телефон занимает десятки пикселей и теряется при сжатии кадра до входа
        модели. Кассир онлайн-оценивается как человек, дольше всех присутствующий в кадре.
        """
        target = max(persons, key=lambda p: presence.get(p.track_id, 0.0))
        if presence.get(target.track_id, 0.0) < 1.0:
            return objects
        height, width = image.shape[:2]
        x1, y1, x2, y2 = target.box
        side = max(1.8 * (x2 - x1), 1.8 * (y2 - y1), 320.0)
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        left, top = int(max(0.0, cx - side / 2)), int(max(0.0, cy - side / 2))
        right, bottom = int(min(width, cx + side / 2)), int(min(height, cy + side / 2))
        if (right - left) * (bottom - top) > 0.5 * width * height or right - left < 32 or bottom - top < 32:
            return objects

        merged = list(objects)
        for det in self.detector.detect(image[top:bottom, left:right]):
            if det.label == "person":
                continue
            box = (det.box[0] + left, det.box[1] + top, det.box[2] + left, det.box[3] + top)
            candidate = ObjectObs(det.label, box, det.confidence)
            duplicate = next((k for k, o in enumerate(merged)
                              if o.label == det.label and box_iou(o.box, box) > 0.4), None)
            if duplicate is None:
                merged.append(candidate)
            elif det.confidence > merged[duplicate].confidence:
                merged[duplicate] = candidate
        return merged

    def _layout(self, records: list[FrameRecord], valid: np.ndarray, width: int, height: int,
                duration: float, step: float) -> ZoneLayout | None:
        if self.zones_file is not None:
            scale = person_scale(records) or 0.25 * float(np.hypot(width, height))
            return ZoneLayout.from_file(self.zones_file, width, height, scale)
        return calibrate_layout(records, valid, width, height, duration, step, self.config)

    def _postprocess(self, events: list[Event]) -> list[Event]:
        """Склейка близких событий одного типа и ограничение их количества."""
        cfg = self.config
        result: list[Event] = []
        by_type: dict[str, list[Event]] = {}
        for event in events:
            by_type.setdefault(event.vtype.code, []).append(event)
        for items in by_type.values():
            items.sort(key=lambda e: e.start_sec)
            merged: list[Event] = []
            for event in items:
                if merged and event.start_sec <= merged[-1].end_sec + cfg.merge_gap_sec:
                    previous = merged[-1]
                    base = event if event.confidence > previous.confidence else previous
                    base.end_sec = max(previous.end_sec, event.end_sec)
                    merged[-1] = base
                else:
                    merged.append(event)
            merged.sort(key=lambda e: -e.confidence)
            result.extend(merged[:cfg.max_events_per_type])
        result.sort(key=lambda e: e.timecode_sec)
        return result

    def _violation(self, event: Event, ctx: RuleContext, cache: FrameCache) -> dict:
        frames = []
        seen: set[int] = set()
        for ref in event.evidence:
            if ref.record_index in seen or len(frames) >= MAX_EVIDENCE_FRAMES:
                continue
            seen.add(ref.record_index)
            record = ctx.records[ref.record_index]
            frames.append({
                "timestamp_sec": round(record.time_sec, 2),
                "image_base64": render_evidence(cache, record, ctx.layout, ref.highlights,
                                                event.vtype.code, self.evidence_annotate,
                                                self.evidence_quality),
            })
        return {
            "type": event.vtype.title,
            "timecode_sec": round(event.timecode_sec, 2),
            "description": f"{event.description} {event.vtype.basis_sentence()}",
            "evidence_frames": frames,
            "code": event.vtype.code,
            "confidence": round(event.confidence, 2),
            "start_sec": round(event.start_sec, 2),
            "end_sec": round(event.end_sec, 2),
            "rule": event.vtype.rule_dict(),
        }

    @staticmethod
    def _timeline_row(record: FrameRecord, state) -> dict:
        return {
            "t": round(record.time_sec, 2),
            "valid": state.valid,
            "persons": len(record.persons),
            "track_ids": [p.track_id for p in record.persons],
            "cashier_present": state.cashier_present,
            "client_present": state.client_present,
            "cashier_side": len(state.cashier_side),
            "phones": len(state.phones),
            "bags": len(state.bags),
            "objects": [f"{o.label}:{o.confidence:.2f}" for o in record.objects],
        }
