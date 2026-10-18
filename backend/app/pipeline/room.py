"""Модель помещения кассы, не зависящая от ракурса камеры.

Вместо «стойки» (вид строго сверху) используется рабочее место кассира: точка, где
дольше всех и с начала записи находится один и тот же человек. Все расстояния
меряются в ростах кассира (высота его бокса), поэтому правила одинаково работают
для камеры сверху, под углом и сбоку.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .geometry import box_intersection_area
from .records import FrameRecord
from .quality import THUMB_WIDTH


def foot(box) -> np.ndarray:
    """Нижняя середина бокса — точка опоры человека (устойчивее центра к наклонам и вставанию)."""
    return np.array([(box[0] + box[2]) / 2.0, box[3]], dtype=np.float64)


@dataclass
class Room:
    anchor: np.ndarray            # точка опоры кассира на рабочем месте (px кадра)
    height: float                 # типичная высота бокса кассира на рабочем месте (px)
    cashier_tracks: set[int]
    frame_size: tuple[int, int]   # (width, height)
    person_ok: list[list[bool]] = field(default_factory=list)  # [record][person] — реальный человек в помещении

    def at_workplace(self, box, radius: float) -> bool:
        return float(np.linalg.norm(foot(box) - self.anchor)) <= radius * self.height

    def thumb_scale(self) -> float:
        return THUMB_WIDTH / float(self.frame_size[0])


def build_room(records: list[FrameRecord], valid: np.ndarray, width: int, height: int,
               duration: float, min_rel_height: float, approach_radius: float = 1.0,
               min_track_conf: float = 0.55) -> Room | None:
    """Находит рабочее место кассира и отфильтровывает «людей за стеклом» и отражения."""
    heights = [p.box[3] - p.box[1] for r, ok in zip(records, valid) if ok for p in r.persons]
    if not heights:
        return None
    reference = float(np.percentile(heights, 75))

    # 1. Фильтр: слишком маленькие фигуры — люди за стеклянной перегородкой или отражения
    person_ok = [[(p.box[3] - p.box[1]) >= min_rel_height * reference for p in r.persons] for r in records]

    # 2. Места: треки, стоящие в одной точке, объединяются (трек рвётся при уходе/окклюзии)
    tracks: dict[int, list[tuple[float, np.ndarray, float, float]]] = {}
    for r, ok_list, ok in zip(records, person_ok, valid):
        if not ok:
            continue
        for p, good in zip(r.persons, ok_list):
            if good:
                tracks.setdefault(p.track_id, []).append(
                    (r.time_sec, foot(p.box), p.box[3] - p.box[1], p.confidence))
    # Отражения в стекле и люди за перегородкой детектируются неуверенно
    confident = {tid: obs for tid, obs in tracks.items() if np.mean([o[3] for o in obs]) >= min_track_conf}
    if not confident:
        return None
    step = float(np.median(np.diff([r.time_sec for r in records]))) if len(records) > 1 else 0.4
    window = max(2.0, 0.1 * duration)
    places: list[dict] = []
    for track_id, obs in sorted(confident.items(), key=lambda item: -len(item[1])):
        times = np.array([o[0] for o in obs])
        points = np.stack([o[1] for o in obs])
        med_h = float(np.median([o[2] for o in obs]))
        center = np.median(points, axis=0)
        place = next((pl for pl in places if np.linalg.norm(pl["center"] - center) <= 0.5 * pl["h"]), None)
        info = {"track": track_id, "span": times[-1] - times[0] + step, "early": times[0] <= window,
                "at_start": times[0] <= 1.0, "late": times[-1] >= duration - window, "h": med_h,
                "spread": float(np.median(np.linalg.norm(points - center, axis=1))) / max(med_h, 1.0)}
        if place is None:
            places.append({"center": center, "h": med_h, "tracks": [info]})
        else:
            place["tracks"].append(info)

    tallest = max(pl["h"] for pl in places)

    def score(place: dict) -> float:
        # Кассир: один длинный непрерывный трек, на месте с первой секунды. На месте клиента
        # люди сменяются (несколько треков), и клиент обычно приходит уже после начала записи.
        infos = place["tracks"]
        longest = max(i["span"] for i in infos) / max(duration, step)
        dwell = min(1.0, sum(i["span"] for i in infos) / max(duration, step))
        still = max(0.0, 1.0 - 3.0 * float(np.mean([i["spread"] for i in infos])))
        long_tracks = sum(1 for i in infos if i["span"] >= 2.0)
        # Уход и возвращение кассира дают два трека на одном месте — это не штрафуем
        return (longest + 0.3 * dwell + 0.8 * any(i["at_start"] for i in infos)
                + 0.1 * any(i["late"] for i in infos) + 0.15 * still
                - 0.25 * max(0, long_tracks - 2) + 0.1 * place["h"] / tallest)

    best = max(places, key=score)
    cashier_tracks = {i["track"] for i in best["tracks"]}
    points = [o[1] for tid in cashier_tracks for o in tracks[tid]
              if np.linalg.norm(o[1] - best["center"]) <= 0.5 * best["h"]]
    anchor = np.median(np.stack(points), axis=0) if points else best["center"]
    h = best["h"]

    # 3. Трек «в помещении» — уверенно детектируемый человек, который подходил к рабочему месту
    #    кассира (клиент, инкассатор, сам кассир). Люди за стеклом и отражения туда не подходят.
    in_room = {tid for tid, obs in confident.items()
               if tid in cashier_tracks
               or min(np.linalg.norm(o[1] - anchor) for o in obs) <= approach_radius * h}
    for r, ok_list in zip(records, person_ok):
        for k, p in enumerate(r.persons):
            ok_list[k] = ok_list[k] and p.track_id in in_room
    return Room(anchor=anchor, height=h, cashier_tracks=cashier_tracks,
                frame_size=(width, height), person_ok=person_ok)


# ----------------------------------------------------------------- сравнение областей
def region_mask(record: FrameRecord, ok: list[bool], scale: float, shape: tuple[int, int]) -> np.ndarray:
    """Маска пикселей миниатюры, не закрытых людьми (с запасом)."""
    free = np.ones(shape, dtype=bool)
    for person, good in zip(record.persons, ok):
        x1, y1, x2, y2 = person.box
        pad_x, pad_y = 0.1 * (x2 - x1), 0.05 * (y2 - y1)
        free[max(0, int((y1 - pad_y) * scale)):int((y2 + pad_y) * scale) + 1,
             max(0, int((x1 - pad_x) * scale)):int((x2 + pad_x) * scale) + 1] = False
    return free


def masked_median(records: list[FrameRecord], room: Room, indices: list[int], box_t: tuple[int, int, int, int],
                  min_cover: float = 0.6) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Медианный вид области (в координатах миниатюры) по кадрам, где её не загораживают люди."""
    x1, y1, x2, y2 = box_t
    stack, masks = [], []
    for i in indices:
        record = records[i]
        mask = region_mask(record, room.person_ok[i], room.thumb_scale(), record.thumb.shape)[y1:y2, x1:x2]
        if mask.size == 0 or mask.mean() < min_cover:
            continue
        stack.append(cv2.GaussianBlur(record.thumb, (3, 3), 0)[y1:y2, x1:x2].astype(np.float32))
        masks.append(mask)
    if not stack:
        return None, None
    data = np.ma.masked_array(np.stack(stack), mask=~np.stack(masks))
    median = np.ma.median(data, axis=0)
    return median.filled(np.nan), ~median.mask if np.ma.is_masked(median) else np.ones(median.shape, bool)


def changed_fraction(before: np.ndarray, after: np.ndarray, threshold: float = 22.0) -> float:
    valid = ~np.isnan(before) & ~np.isnan(after)
    if valid.sum() < 30:
        return 0.0
    # компенсация общего изменения яркости (автоэкспозиция камеры)
    shift = float(np.median(after[valid] - before[valid]))
    return float((np.abs(after[valid] - before[valid] - shift) > threshold).mean())


def to_thumb_box(box, scale: float, shape: tuple[int, int], expand_x: float = 0.0,
                 expand_y: float = 0.0) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    x1, x2 = (x1 - expand_x * w) * scale, (x2 + expand_x * w) * scale
    y1, y2 = (y1 - expand_y * h) * scale, (y2 + expand_y * h) * scale
    return (int(max(0, x1)), int(max(0, y1)), int(min(shape[1], x2)), int(min(shape[0], y2)))


def overlaps_any(box, records_boxes, threshold: float = 0.05) -> bool:
    area = max((box[2] - box[0]) * (box[3] - box[1]), 1.0)
    return any(box_intersection_area(box, other) > threshold * area for other in records_boxes)
