"""Pydantic-схемы ответов API (используются для валидации и документации OpenAPI)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeResponse(BaseModel):
    job_id: str = Field(examples=["3f2a9c1e5b7d4a60"])


class EvidenceFrame(BaseModel):
    timestamp_sec: float = Field(description="Время кадра от начала видео, с")
    image_base64: str = Field(description="JPEG-кадр в base64")


class RuleReference(BaseModel):
    document: str
    act: str
    clause: str
    requirement: str
    url: str


class Violation(BaseModel):
    type: str = Field(description="Тип нарушения")
    timecode_sec: float = Field(description="Таймкод события от начала видео, с")
    description: str = Field(description="Что видно на видео и почему это может быть нарушением")
    evidence_frames: list[EvidenceFrame] = Field(description="1–3 кадра-доказательства")
    code: str = Field(description="Машинный код типа нарушения")
    confidence: float = Field(ge=0, le=1)
    start_sec: float
    end_sec: float
    rule: RuleReference


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    status: Literal["processing", "done", "failed"]
    verdict: Literal["violation", "no_violation"] | None = None
    violations: list[Violation] | None = None
    progress: float | None = Field(default=None, description="0..1, пока status=processing")
    stage: str | None = None
    queue_position: int | None = None
    error: str | None = None
    processing_time_sec: float | None = None
    filename: str | None = None
    video: dict | None = None
    analysis: dict | None = None


class ViolationTypeInfo(BaseModel):
    code: str
    type: str
    detects: str
    rule: RuleReference
