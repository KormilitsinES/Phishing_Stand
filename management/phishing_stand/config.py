"""Модель конфигурации стенда. Читает .env и валидирует значения."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# Паттерны для валидации
_DOMAIN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$"
)
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
_IPV4_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)


class Settings(BaseModel):
    """Полная конфигурация стенда."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    # Домены
    BASE_DOMAIN: str = Field(..., description="Базовый домен (example.com)")
    TRACK_DOMAIN: str = Field(..., description="Домен для трекинга Gophish")
    EVIL_DOMAIN: str = Field(..., description="Домен для Evilginx2")
    MX_DOMAIN: str = Field(..., description="Домен для почтового шлюза")

    # Админ и сеть
    ADMIN_EMAIL: str = Field(..., description="Email администратора")
    VPS_IP: str = Field(..., description="Публичный IP сервера")

    # Опциональные параметры с дефолтами
    GOPHISH_BACKEND: str = Field(default="gophish")
    POSTFIX_BACKEND: str = Field(default="postfix")
    EVILGINX_BACKEND: str = Field(default="evilginx2")

    @field_validator("BASE_DOMAIN", "TRACK_DOMAIN", "EVIL_DOMAIN", "MX_DOMAIN")
    @classmethod
    def _validate_domain(cls, v: str, info) -> str:  # noqa: N805
        if not _DOMAIN_RE.match(v):
            raise ValueError(f"Некорректный домен в поле {info.field_name}: {v!r}")
        return v.lower()

    @field_validator("ADMIN_EMAIL")
    @classmethod
    def _validate_email(cls, v: str) -> str:  # noqa: N805
        if not _EMAIL_RE.match(v):
            raise ValueError(f"Некорректный email: {v!r}")
        return v.lower()

    @field_validator("VPS_IP")
    @classmethod
    def _validate_ip(cls, v: str) -> str:  # noqa: N805
        if not _IPV4_RE.match(v):
            raise ValueError(f"Некорректный IPv4: {v!r}")
        return v

    @classmethod
    def from_env_file(cls, path: Path | None = None) -> Self:
        """Загрузить конфигурацию из .env файла."""
        from dotenv import dotenv_values

        path = path or Path.cwd() / ".env"
        if not path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {path}")

        raw = dotenv_values(path)
        # Отфильтровываем None-значения (пустые строки в .env)
        data = {k: v for k, v in raw.items() if v is not None}
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Ошибки валидации конфигурации:\n{e}") from e

    @classmethod
    def from_env_file_or_none(cls, path: Path | None = None) -> Self | None:
        """Загрузить конфигурацию, вернуть None при отсутствии/ошибке."""
        try:
            return cls.from_env_file(path)
        except (FileNotFoundError, ValueError):
            return None