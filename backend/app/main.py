"""Точка входа FastAPI. Запуск: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router
from .config import Settings, load_settings
from .jobs import JobManager, JobStore
from .pipeline.analyzer import VideoAnalyzer
from .pipeline.detector import create_detector
from .pipeline.rule_config import load_rule_config
from .pipeline.rules import default_rules, overhead_rules

logger = logging.getLogger("app")


def build_analyzer(settings: Settings) -> VideoAnalyzer:
    config = load_rule_config(settings.rules_file)
    # Модель общая для всех воркеров: делим ядра между одновременными задачами
    threads = settings.detector_threads or max(1, (os.cpu_count() or 2) // settings.max_concurrent_jobs)
    detector = create_detector(
        settings.detector_backend,
        settings.model_path,
        config.detector_labels,
        score_threshold=config.detector_min_conf,
        threads=threads,
    )
    return VideoAnalyzer(
        detector=detector,
        config=config,
        analysis_fps=settings.analysis_fps,
        max_analyzed_frames=settings.max_analyzed_frames,
        budget_sec=settings.processing_budget_sec,
        zones_file=settings.zones_file,
        evidence_max_width=settings.evidence_max_width,
        evidence_quality=settings.evidence_jpeg_quality,
        evidence_annotate=settings.evidence_annotate,
        object_zoom=settings.object_zoom,
        rules=overhead_rules() if settings.ruleset == "overhead" else default_rules(),
    )


def create_app(settings: Settings | None = None, analyzer: VideoAnalyzer | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        active_analyzer = analyzer or build_analyzer(settings)
        logger.info("Детектор: %s", active_analyzer.detector.name)
        manager = JobManager(settings, active_analyzer, JobStore(settings.jobs_dir))
        manager.start()
        app.state.jobs = manager
        app.state.detector_name = active_analyzer.detector.name
        try:
            yield
        finally:
            manager.stop()

    app = FastAPI(
        title="Cash Discipline Monitor API",
        version=__version__,
        description=(
            "Локальный AI-сервис выявления визуально наблюдаемых признаков нарушений кассовой "
            "дисциплины. Все запросы к /api/v1 требуют заголовок X-API-Key. "
            "Результат — подсказка для проверки человеком, а не юридическое заключение."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type"],
    )
    app.include_router(router)

    @app.get("/api/health", tags=["service"], summary="Проверка доступности (без ключа)")
    def health() -> dict:
        return {"status": "ok", "version": __version__,
                "detector": getattr(app.state, "detector_name", None)}

    if settings.static_dir and settings.static_dir.is_dir():
        # Опционально: сервер отдаёт собранный фронтенд (деплой одним контейнером)
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")

    return app
