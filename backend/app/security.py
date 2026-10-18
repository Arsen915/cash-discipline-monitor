"""Проверка API-ключа из заголовка X-API-Key."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Ключ доступа к API, выданный командой",
)


def require_api_key(request: Request, api_key: str | None = Security(api_key_header)) -> str:
    valid_keys: tuple[str, ...] = request.app.state.settings.api_keys
    if api_key:
        provided = api_key.encode("utf-8")
        # compare_digest по всем ключам, чтобы время ответа не зависело от совпадения
        matches = [secrets.compare_digest(provided, key.encode("utf-8")) for key in valid_keys]
        if any(matches):
            return api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный или отсутствующий API-ключ (заголовок X-API-Key)",
        headers={"WWW-Authenticate": "ApiKey"},
    )
