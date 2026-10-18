"""Настройки сервиса. Все значения читаются из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ALLOWED_VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v", ".avi", ".mkv")


def _get(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _int(name: str, default: int) -> int:
    value = _get(name)
    return int(value) if value is not None else default


def _float(name: str, default: float) -> float:
    value = _get(name)
    return float(value) if value is not None else default


def _bool(name: str, default: bool) -> bool:
    value = _get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str | None) -> Path | None:
    value = _get(name) or default
    return Path(value).expanduser().resolve() if value else None


@dataclass(frozen=True)
class Settings:
    api_keys: tuple[str, ...]
    data_dir: Path
    model_path: Path
    detector_backend: str
    detector_threads: int
    object_zoom: bool
    max_concurrent_jobs: int
    max_upload_mb: int
    analysis_fps: float
    max_analyzed_frames: int
    processing_budget_sec: float
    keep_uploads: bool
    job_ttl_hours: float
    zones_file: Path | None
    rules_file: Path | None
    cors_origins: tuple[str, ...]
    static_dir: Path | None
    evidence_max_width: int
    evidence_jpeg_quality: int
    evidence_annotate: bool
    log_level: str

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    raw_keys = _get("API_KEYS") or _get("API_KEY") or ""
    api_keys = tuple(key.strip() for key in raw_keys.split(",") if key.strip())
    if not api_keys:
        raise RuntimeError(
            "Не задан API-ключ: укажите переменную окружения API_KEY "
            "(или несколько ключей через запятую в API_KEYS)"
        )

    backend_root = Path(__file__).resolve().parent.parent
    cpu_count = os.cpu_count() or 2
    cors = _get("CORS_ORIGINS") or "*"

    return Settings(
        api_keys=api_keys,
        data_dir=_path("DATA_DIR", str(backend_root / "data")),
        model_path=_path("MODEL_PATH", str(backend_root / "models" / "yolox_tiny.onnx")),
        detector_backend=(_get("DETECTOR_BACKEND") or "yolox").lower(),
        detector_threads=_int("DETECTOR_THREADS", 0),
        object_zoom=_bool("OBJECT_ZOOM", True),
        max_concurrent_jobs=max(1, _int("MAX_CONCURRENT_JOBS", min(2, cpu_count))),
        max_upload_mb=_int("MAX_UPLOAD_MB", 500),
        analysis_fps=_float("ANALYSIS_FPS", 3.0),
        max_analyzed_frames=_int("MAX_ANALYZED_FRAMES", 450),
        processing_budget_sec=_float("PROCESSING_BUDGET_SEC", 55.0),
        keep_uploads=_bool("KEEP_UPLOADS", False),
        job_ttl_hours=_float("JOB_TTL_HOURS", 24.0),
        zones_file=_path("ZONES_FILE", None),
        rules_file=_path("RULES_FILE", None),
        cors_origins=tuple(origin.strip() for origin in cors.split(",") if origin.strip()),
        static_dir=_path("STATIC_DIR", None),
        evidence_max_width=_int("EVIDENCE_MAX_WIDTH", 960),
        evidence_jpeg_quality=_int("EVIDENCE_JPEG_QUALITY", 82),
        evidence_annotate=_bool("EVIDENCE_ANNOTATE", True),
        log_level=(_get("LOG_LEVEL") or "INFO").upper(),
    )
