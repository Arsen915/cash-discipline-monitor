"""Зоны кассы: сторона кассира (за стойкой), рабочее место, клиентская зона у стойки, стол.

Два режима:
* manual — полигоны из JSON-файла (ZONES_FILE) в нормированных координатах 0..1.
  Для стационарной камеры банка это основной режим: зоны размечаются один раз.
* auto — автокалибровка по траекториям людей в самом видео. Нужна, когда ракурс
  заранее неизвестен (финальное тестовое видео снято под другим углом).

Автокалибровка: кассир — человек, который дольше всех неподвижно присутствует в
кадре с начала записи; клиентская точка — наиболее «насиженное» место других людей
рядом с кассиром. Стойка — серединный перпендикуляр между ними.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .geometry import (
    circle_polygon,
    clip_halfplane,
    clip_to_frame,
    frame_polygon,
    oriented_rect,
    point_in_polygon,
)
from .records import FrameRecord
from .rule_config import RuleConfig


@dataclass
class ZoneLayout:
    width: int
    height: int
    cashier_side: np.ndarray
    workplace: np.ndarray
    client_counter: np.ndarray
    desk: np.ndarray | None
    source: str
    person_scale: float
    notes: list[str] = field(default_factory=list)

    def in_cashier_side(self, point) -> bool:
        return point_in_polygon(self.cashier_side, point)

    def in_workplace(self, point) -> bool:
        return point_in_polygon(self.workplace, point)

    def in_client_counter(self, point) -> bool:
        return point_in_polygon(self.client_counter, point) and not self.in_cashier_side(point)

    def to_dict(self) -> dict:
        def norm(polygon: np.ndarray | None):
            if polygon is None:
                return None
            return [[round(float(x) / self.width, 4), round(float(y) / self.height, 4)]
                    for x, y in polygon]

        return {
            "source": self.source,
            "cashier_side": norm(self.cashier_side),
            "workplace": norm(self.workplace),
            "client_counter": norm(self.client_counter),
            "desk": norm(self.desk),
            "notes": self.notes,
        }

    @classmethod
    def from_file(cls, path: Path, width: int, height: int, person_scale: float) -> "ZoneLayout":
        data = json.loads(path.read_text(encoding="utf-8"))

        def polygon(name: str, required: bool) -> np.ndarray | None:
            points = data.get(name)
            if not points:
                if required:
                    raise ValueError(f"В {path} не задана обязательная зона '{name}'")
                return None
            array = np.array(points, dtype=np.float64)
            if array.ndim != 2 or array.shape[1] != 2 or len(array) < 3:
                raise ValueError(f"Зона '{name}' должна быть списком из ≥3 точек [x, y]")
            return array * np.array([width, height])

        cashier_side = polygon("cashier_side", required=True)
        client_counter = polygon("client_counter", required=True)
        workplace = polygon("workplace", required=False)
        return cls(
            width=width,
            height=height,
            cashier_side=cashier_side,
            workplace=workplace if workplace is not None else cashier_side,
            client_counter=client_counter,
            desk=polygon("desk", required=False),
            source="manual",
            person_scale=person_scale,
            notes=[f"Зоны загружены из {path.name}"],
        )


def person_scale(records: list[FrameRecord]) -> float | None:
    diags = [p.diag for r in records for p in r.persons]
    return float(np.median(diags)) if diags else None


def _track_points(records: list[FrameRecord]) -> dict[int, list[tuple[float, np.ndarray]]]:
    tracks: dict[int, list[tuple[float, np.ndarray]]] = {}
    for record in records:
        for person in record.persons:
            tracks.setdefault(person.track_id, []).append((record.time_sec, person.center))
    return tracks


def calibrate_layout(records: list[FrameRecord], valid: np.ndarray, width: int, height: int,
                     duration: float, step: float, config: RuleConfig) -> ZoneLayout | None:
    usable = [r for r, ok in zip(records, valid) if ok]
    scale = person_scale(usable)
    if scale is None:
        return None
    tracks = _track_points(usable)
    notes: list[str] = []

    # --- 1. Места: треки, стоящие в одной точке, объединяем (трек кассира рвётся, когда он уходит)
    window = max(2.0, 0.1 * duration)
    border = 0.6 * scale
    places: list[dict] = []
    for track_id, observations in sorted(tracks.items(), key=lambda item: -len(item[1])):
        times = np.array([t for t, _ in observations])
        points = np.stack([p for _, p in observations])
        median_point = np.median(points, axis=0)
        first = points[0]
        info = {
            "track": track_id,
            "span": times[-1] - times[0] + step,
            "early": times[0] <= window,
            "late": times[-1] >= duration - window,
            "spread": float(np.median(np.linalg.norm(points - median_point, axis=1))) / scale,
            "from_edge": times[0] > window
            and min(first[0], first[1], width - first[0], height - first[1]) < border,
        }
        place = next((pl for pl in places if np.linalg.norm(pl["center"] - median_point) <= 0.8 * scale), None)
        if place is None:
            places.append({"center": median_point, "tracks": [info]})
        else:
            place["tracks"].append(info)

    # --- 2. Кассир: место с наибольшим суммарным присутствием, занятое с начала/до конца записи,
    #        где люди стоят неподвижно и не «входят» с края кадра
    def place_score(place: dict) -> float:
        infos = place["tracks"]
        dwell = min(1.0, sum(i["span"] for i in infos) / max(duration, step))
        stationarity = max(0.0, 1.0 - float(np.mean([i["spread"] for i in infos])))
        edge_share = float(np.mean([i["from_edge"] for i in infos]))
        return (dwell + 0.35 * any(i["early"] for i in infos) + 0.15 * any(i["late"] for i in infos)
                + 0.25 * stationarity - 0.35 * edge_share)

    cashier_place = max(places, key=place_score)
    cashier_tracks = {info["track"] for info in cashier_place["tracks"]}
    anchor = np.median(np.stack([p for tid in cashier_tracks for _, p in tracks[tid]]), axis=0)

    # --- 3. Клиентская точка у стойки: наиболее заселённое место других людей рядом с кассиром
    others = [p for track_id, observations in tracks.items() if track_id not in cashier_tracks
              for _, p in observations
              if 1.0 * scale <= np.linalg.norm(p - anchor) <= 4.5 * scale]
    client_point = None
    if len(others) >= 3:
        points = np.stack(others)
        cell = 0.5 * scale
        keys = np.floor(points / cell).astype(int)
        unique, counts = np.unique(keys, axis=0, return_counts=True)
        densest = (unique[np.argmax(counts)] + 0.5) * cell
        close = points[np.linalg.norm(points - densest, axis=1) <= 0.8 * scale]
        client_point = close.mean(axis=0) if len(close) else densest

    if client_point is not None:
        axis = client_point - anchor
        distance = float(np.linalg.norm(axis))
        axis = axis / distance
        counter_offset = float(np.clip(0.5 * distance, 0.55 * scale, max(distance - 0.4 * scale, 0.55 * scale)))
        source = "auto"
        notes.append("Стойка определена между рабочим местом кассира и местом клиента")
    else:
        to_center = np.array([width / 2.0, height / 2.0]) - anchor
        if np.linalg.norm(to_center) < 0.5 * scale:
            to_center = np.array([0.0, 1.0])
        axis = to_center / np.linalg.norm(to_center)
        distance = 2.2 * scale
        client_point = anchor + axis * distance
        counter_offset = 1.0 * scale
        source = "auto-fallback"
        notes.append("Клиенты не обнаружены: клиентская зона предположена в сторону центра кадра")

    frame = frame_polygon(width, height)
    line_offset = float(np.dot(anchor, axis)) + counter_offset
    cashier_side = clip_halfplane(frame, axis, line_offset)
    workplace = clip_to_frame(
        clip_halfplane(circle_polygon(anchor, config.workplace_radius * scale), axis, line_offset),
        width, height)
    client_radius = max(config.client_radius * scale, 0.6 * distance)
    client_counter = clip_to_frame(
        clip_halfplane(circle_polygon(client_point, client_radius), -axis, -line_offset),
        width, height)
    desk = clip_to_frame(
        oriented_rect(anchor, axis, (counter_offset - 0.7 * scale, counter_offset + 0.15 * scale),
                      (-1.1 * scale, 1.1 * scale)),
        width, height)

    return ZoneLayout(
        width=width,
        height=height,
        cashier_side=cashier_side,
        workplace=workplace,
        client_counter=client_counter,
        desk=desk if len(desk) >= 3 else None,
        source=source,
        person_scale=scale,
        notes=notes,
    )
