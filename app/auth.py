"""Xác thực bằng khóa API trong header X-API-Key."""

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided_key: str | None = Security(api_key_header)) -> None:
    """Dùng làm dependency: không có khóa đúng thì trả 401 và endpoint không chạy."""
    expected = settings.app_api_key.encode()
    if not provided_key or not secrets.compare_digest(provided_key.encode(), expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")