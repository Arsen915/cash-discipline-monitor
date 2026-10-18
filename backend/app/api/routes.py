"""REST API v1: загрузка видео и получение результата по job_id."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from ..config import ALLOWED_VIDEO_EXTENSIONS
from ..jobs import JobManager, new_job_id
from ..pipeline.rules import catalog_as_dict
from ..schemas import AnalyzeResponse, JobResponse, ViolationTypeInfo
from ..security import require_api_key

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)], tags=["analysis"])

_CHUNK = 1024 * 1024


def _jobs(request: Request) -> JobManager:
    return request.app.state.jobs


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Загрузить видео (.mov) на анализ",
    responses={
        401: {"description": "Неверный или отсутствующий X-API-Key"},
        413: {"description": "Файл превышает допустимый размер"},
        415: {"description": "Неподдерживаемый формат файла"},
    },
)
def analyze(request: Request, file: UploadFile = File(..., description="Видеофайл .mov")):
    settings = request.app.state.settings
    filename = Path(file.filename or "video.mov").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Ожидается видеофайл {', '.join(ALLOWED_VIDEO_EXTENSIONS)}; получен «{extension or 'без расширения'}»",
        )

    job_id = new_job_id()
    destination = settings.uploads_dir / f"{job_id}{extension}"
    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with destination.open("wb") as target:
            while chunk := file.file.read(_CHUNK):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                        f"Файл больше {settings.max_upload_mb} МБ")
                target.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    if written == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Загружен пустой файл")

    _jobs(request).submit(job_id, destination, filename)
    return AnalyzeResponse(job_id=job_id)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    response_model_exclude_none=True,
    summary="Статус обработки и результат",
    responses={404: {"description": "Задача не найдена"}},
)
def get_job(job_id: str, request: Request):
    job = _jobs(request).get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    return job


@router.get("/violation-types", response_model=list[ViolationTypeInfo],
            summary="Распознаваемые типы нарушений и нормативные основания")
def violation_types():
    return catalog_as_dict()
