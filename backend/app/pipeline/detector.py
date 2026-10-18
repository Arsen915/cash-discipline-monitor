"""Детекторы объектов (люди, телефоны, сумки), работающие полностью локально.

По умолчанию — YOLOX (Apache-2.0) в формате ONNX через onnxruntime на CPU:
лицензия разрешает коммерческое использование, PyTorch в рантайме не нужен.
Опционально — Ultralytics YOLO (AGPL-3.0), если пакет ultralytics установлен.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

COCO_CLASSES: tuple[str, ...] = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
)


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 в пикселях исходного кадра


class Detector(ABC):
    name: str = "detector"

    @abstractmethod
    def detect(self, image: np.ndarray) -> list[Detection]:
        """Детекции на BGR-кадре."""


def _clip_box(box: np.ndarray, width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    return (
        float(np.clip(x1, 0, width - 1)),
        float(np.clip(y1, 0, height - 1)),
        float(np.clip(x2, 0, width - 1)),
        float(np.clip(y2, 0, height - 1)),
    )


class YoloxOnnxDetector(Detector):
    """YOLOX, экспортированный в ONNX (официальные веса Megvii, обучены на COCO)."""

    def __init__(
        self,
        model_path: Path,
        labels: Iterable[str],
        score_threshold: float = 0.25,
        nms_threshold: float = 0.45,
        threads: int = 0,
    ):
        import onnxruntime as ort

        if not model_path.is_file():
            raise FileNotFoundError(
                f"Файл модели не найден: {model_path}. Запустите scripts/download_models.py"
            )
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if threads > 0:
            options.intra_op_num_threads = threads
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        model_input = self._session.get_inputs()[0]
        self._input_name = model_input.name
        shape = model_input.shape
        height = shape[2] if isinstance(shape[2], int) else 640
        width = shape[3] if isinstance(shape[3], int) else 640
        self._input_hw = (height, width)
        self._grids, self._strides = self._make_grids(height, width)

        unknown = [label for label in labels if label not in COCO_CLASSES]
        if unknown:
            raise ValueError(f"Неизвестные классы COCO: {unknown}")
        self._labels = list(dict.fromkeys(labels))
        self._class_ids = np.array([COCO_CLASSES.index(label) for label in self._labels])
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.name = f"YOLOX-ONNX ({model_path.name}, вход {width}x{height})"

    @staticmethod
    def _make_grids(height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
        grids, strides = [], []
        for stride in (8, 16, 32):
            hsize, wsize = height // stride, width // stride
            xv, yv = np.meshgrid(np.arange(wsize), np.arange(hsize))
            grid = np.stack((xv, yv), axis=2).reshape(-1, 2)
            grids.append(grid)
            strides.append(np.full((grid.shape[0], 1), stride))
        return (
            np.concatenate(grids, axis=0).astype(np.float32),
            np.concatenate(strides, axis=0).astype(np.float32),
        )

    def _preprocess(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        # Letterbox с паддингом 114 и без нормализации — как в официальной демо YOLOX
        in_h, in_w = self._input_hw
        ratio = min(in_h / image.shape[0], in_w / image.shape[1])
        new_w, new_h = int(image.shape[1] * ratio), int(image.shape[0] * ratio)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        padded = np.full((in_h, in_w, 3), 114, dtype=np.uint8)
        padded[:new_h, :new_w] = resized
        blob = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)
        return blob[None], ratio

    def detect(self, image: np.ndarray) -> list[Detection]:
        blob, ratio = self._preprocess(image)
        raw = self._session.run(None, {self._input_name: blob})[0][0]

        centers = (raw[:, :2] + self._grids) * self._strides
        sizes = np.exp(np.clip(raw[:, 2:4], -10.0, 10.0)) * self._strides
        boxes = np.concatenate([centers - sizes / 2, centers + sizes / 2], axis=1) / ratio
        scores = raw[:, 5:][:, self._class_ids] * raw[:, 4:5]

        height, width = image.shape[:2]
        detections: list[Detection] = []
        for column, label in enumerate(self._labels):
            class_scores = scores[:, column]
            mask = class_scores >= self.score_threshold
            if not np.any(mask):
                continue
            class_boxes = boxes[mask]
            class_scores = class_scores[mask]
            rects = np.column_stack(
                [class_boxes[:, 0], class_boxes[:, 1],
                 class_boxes[:, 2] - class_boxes[:, 0], class_boxes[:, 3] - class_boxes[:, 1]]
            )
            keep = cv2.dnn.NMSBoxes(
                rects.tolist(), class_scores.tolist(), self.score_threshold, self.nms_threshold
            )
            for index in np.array(keep, dtype=int).flatten():
                detections.append(
                    Detection(label, float(class_scores[index]),
                              _clip_box(class_boxes[index], width, height))
                )
        return detections


class UltralyticsDetector(Detector):
    """Ultralytics YOLO (.pt/.onnx). Пакет ultralytics распространяется под AGPL-3.0."""

    def __init__(self, model_path: Path, labels: Iterable[str], score_threshold: float = 0.25,
                 image_size: int = 640):
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - зависит от окружения
            raise RuntimeError(
                "DETECTOR_BACKEND=ultralytics требует пакет ultralytics: pip install ultralytics"
            ) from exc
        self._model = YOLO(str(model_path))
        wanted = set(labels)
        names: dict[int, str] = self._model.names
        self._class_ids = [class_id for class_id, name in names.items() if name in wanted]
        if not self._class_ids:
            raise ValueError("Модель Ultralytics не содержит ни одного из нужных классов")
        self._names = names
        self._threshold = score_threshold
        self._image_size = image_size
        # Предиктор Ultralytics хранит состояние, поэтому вызовы сериализуем
        self._lock = threading.Lock()
        self.name = f"Ultralytics YOLO ({model_path.name})"

    def detect(self, image: np.ndarray) -> list[Detection]:
        with self._lock:
            result = self._model.predict(image, imgsz=self._image_size, conf=self._threshold,
                                         classes=self._class_ids, verbose=False)[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        height, width = image.shape[:2]
        xyxy = boxes.xyxy.cpu().numpy()
        confidences = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)
        return [
            Detection(self._names[int(class_id)], float(conf), _clip_box(box, width, height))
            for box, conf, class_id in zip(xyxy, confidences, classes)
        ]


def create_detector(backend: str, model_path: Path, labels: Iterable[str], score_threshold: float,
                    threads: int = 0) -> Detector:
    labels = list(labels)
    if backend == "yolox":
        return YoloxOnnxDetector(model_path, labels, score_threshold=score_threshold, threads=threads)
    if backend == "ultralytics":
        return UltralyticsDetector(model_path, labels, score_threshold=score_threshold)
    raise ValueError(f"Неизвестный DETECTOR_BACKEND: {backend!r} (допустимо: yolox, ultralytics)")
