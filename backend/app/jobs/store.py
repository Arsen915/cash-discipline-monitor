"""Хранилище задач: в памяти + JSON-файлы на диске (переживает перезапуск сервиса)."""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

logger = logging.getLogger(__name__)

QUEUED, PROCESSING, DONE, FAILED = "queued", "processing", "done", "failed"


def new_job_id() -> str:
    return secrets.token_hex(8)


@dataclass
class Job:
    job_id: str
    filename: str
    video_path: str | None
    status: str = QUEUED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    progress: float = 0.0
    stage: str = "В очереди"
    result: dict | None = None
    error: str | None = None

    def public(self, queue_position: int | None = None) -> dict:
        """Ответ GET /api/v1/jobs/{job_id}. Внутренний статус queued отдаётся как processing."""
        data: dict = {
            "job_id": self.job_id,
            "status": PROCESSING if self.status in (QUEUED, PROCESSING) else self.status,
        }
        if self.status == DONE and self.result is not None:
            data["verdict"] = self.result["verdict"]
            data["violations"] = self.result["violations"]
            data["video"] = self.result.get("video")
            data["analysis"] = self.result.get("analysis")
            if self.started_at and self.finished_at:
                data["processing_time_sec"] = round(self.finished_at - self.started_at, 2)
        elif self.status == FAILED:
            data["error"] = self.error or "Неизвестная ошибка обработки"
        else:
            data["progress"] = round(self.progress, 3)
            data["stage"] = self.stage
            if self.status == QUEUED and queue_position is not None:
                data["queue_position"] = queue_position
        data["filename"] = self.filename
        return data


class JobStore:
    def __init__(self, directory: Path):
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def _file(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.json"

    def _persist(self, job: Job) -> None:
        target = self._file(job.job_id)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(job), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist(job)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return Job(**asdict(job)) if job else None

    def update(self, job_id: str, persist: bool = True, **changes) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for name, value in changes.items():
                setattr(job, name, value)
            job.updated_at = time.time()
            if persist:
                self._persist(job)

    def load(self) -> list[Job]:
        """Поднимает задачи с диска при старте сервиса."""
        known = {f.name for f in fields(Job)}
        loaded: list[Job] = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                job = Job(**{k: v for k, v in raw.items() if k in known})
            except (OSError, ValueError, TypeError):
                logger.warning("Повреждённый файл задачи пропущен: %s", path.name)
                continue
            loaded.append(job)
        with self._lock:
            for job in loaded:
                self._jobs[job.job_id] = job
        return loaded

    def purge(self, max_age_sec: float) -> list[Job]:
        """Удаляет завершённые задачи старше max_age_sec. Возвращает удалённые."""
        threshold = time.time() - max_age_sec
        with self._lock:
            expired = [job for job in self._jobs.values()
                       if job.status in (DONE, FAILED) and job.updated_at < threshold]
            for job in expired:
                del self._jobs[job.job_id]
                self._file(job.job_id).unlink(missing_ok=True)
        return expired
