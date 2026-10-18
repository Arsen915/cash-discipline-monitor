"""Очередь задач и пул рабочих потоков.

Используются потоки, а не процессы: onnxruntime и OpenCV отпускают GIL на тяжёлых
операциях, а модель загружается в память один раз и разделяется между воркерами.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

from ..config import Settings
from ..pipeline.analyzer import VideoAnalyzer
from ..pipeline.video import VideoError
from .store import DONE, FAILED, PROCESSING, QUEUED, Job, JobStore

logger = logging.getLogger(__name__)

_STOP = object()


class JobManager:
    def __init__(self, settings: Settings, analyzer: VideoAnalyzer, store: JobStore):
        self._settings = settings
        self._analyzer = analyzer
        self._store = store
        self._queue: queue.Queue = queue.Queue()
        self._pending: list[str] = []
        self._pending_lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._recover()
        for number in range(self._settings.max_concurrent_jobs):
            thread = threading.Thread(target=self._worker, name=f"analyzer-{number}", daemon=True)
            thread.start()
            self._threads.append(thread)
        janitor = threading.Thread(target=self._janitor, name="janitor", daemon=True)
        janitor.start()
        self._threads.append(janitor)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        for _ in range(self._settings.max_concurrent_jobs):
            self._queue.put(_STOP)
        for thread in self._threads:
            thread.join(timeout=timeout)

    def _recover(self) -> None:
        for job in self._store.load():
            if job.status not in (QUEUED, PROCESSING):
                continue
            if job.video_path and Path(job.video_path).is_file():
                self._store.update(job.job_id, status=QUEUED, progress=0.0, stage="В очереди (после перезапуска)")
                self._enqueue(job.job_id)
            else:
                self._store.update(job.job_id, status=FAILED,
                                   error="Обработка прервана перезапуском сервиса, видео недоступно")

    # ------------------------------------------------------------------- public
    def submit(self, job_id: str, video_path: Path, filename: str) -> Job:
        job = Job(job_id=job_id, filename=filename, video_path=str(video_path))
        self._store.add(job)
        self._enqueue(job_id)
        return job

    def get(self, job_id: str) -> dict | None:
        job = self._store.get(job_id)
        if job is None:
            return None
        position = None
        if job.status == QUEUED:
            with self._pending_lock:
                position = self._pending.index(job_id) + 1 if job_id in self._pending else None
        return job.public(position)

    # ------------------------------------------------------------------ workers
    def _enqueue(self, job_id: str) -> None:
        with self._pending_lock:
            self._pending.append(job_id)
        self._queue.put(job_id)

    def _worker(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if item is _STOP:
                return
            with self._pending_lock:
                if item in self._pending:
                    self._pending.remove(item)
            try:
                self._process(item)
            except Exception:  # воркер не должен умирать ни при каких ошибках
                logger.exception("Необработанная ошибка в задаче %s", item)

    def _process(self, job_id: str) -> None:
        job = self._store.get(job_id)
        if job is None or job.video_path is None:
            return
        video_path = Path(job.video_path)
        self._store.update(job_id, status=PROCESSING, started_at=time.time(), progress=0.01,
                           stage="Подготовка")
        logger.info("Задача %s: старт анализа %s", job_id, job.filename)

        def progress(fraction: float, stage: str) -> None:
            self._store.update(job_id, persist=False, progress=fraction, stage=stage)

        try:
            result = self._analyzer.analyze(video_path, progress=progress)
        except VideoError as exc:
            self._store.update(job_id, status=FAILED, finished_at=time.time(), error=str(exc))
            logger.warning("Задача %s: ошибка видео: %s", job_id, exc)
        except Exception as exc:
            logger.exception("Задача %s: ошибка анализа", job_id)
            self._store.update(job_id, status=FAILED, finished_at=time.time(),
                               error=f"Внутренняя ошибка анализа ({type(exc).__name__})")
        else:
            self._store.update(job_id, status=DONE, finished_at=time.time(), progress=1.0,
                               stage="Готово", result=result)
            logger.info("Задача %s: готово, вердикт=%s, нарушений=%d", job_id, result["verdict"],
                        len(result["violations"]))
        finally:
            if not self._settings.keep_uploads:
                video_path.unlink(missing_ok=True)
                self._store.update(job_id, video_path=None)

    def _janitor(self) -> None:
        ttl = self._settings.job_ttl_hours * 3600
        while not self._stop.wait(600):
            for job in self._store.purge(ttl):
                if job.video_path:
                    Path(job.video_path).unlink(missing_ok=True)
