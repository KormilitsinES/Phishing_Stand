"""Централизованное логирование на базе rich."""
from __future__ import annotations

import logging
import sys
from typing import Final

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Кастомная тема для единообразия вывода
_THEME: Final[Theme] = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "debug": "dim",
        "step": "bold magenta",
    }
)

_CONSOLE: Final[Console] = Console(theme=_THEME, stderr=True)
_CONSOLE_OUT: Final[Console] = Console(theme=_THEME)


class _SuccessLevel:
    """Добавляем кастомный уровень SUCCESS между INFO и WARNING."""

    LEVEL: Final[int] = 25

    @classmethod
    def register(cls) -> None:
        if not logging.getLevelName(cls.LEVEL).startswith("Level"):
            return
        logging.addLevelName(cls.LEVEL, "SUCCESS")

        def success(self: logging.Logger, message: str, *args, **kwargs) -> None:
            if self.isEnabledFor(cls.LEVEL):
                self._log(cls.LEVEL, message, args, **kwargs)

        logging.Logger.success = success  # type: ignore[attr-defined]


_SuccessLevel.register()


def setup_logging(verbose: bool = False) -> None:
    """Инициализирует корневой логгер приложения."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = RichHandler(
        console=_CONSOLE,
        show_time=True,
        show_path=False,
        show_level=True,
        rich_tracebacks=True,
        markup=True,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger("phishing_stand")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Возвращает именованный логгер в пространстве phishing_stand."""
    prefix = "phishing_stand"
    full_name = f"{prefix}.{name}" if name else prefix
    return logging.getLogger(full_name)


def console() -> Console:
    """Console для вывода в stderr (служебные сообщения, прогресс-бары)."""
    return _CONSOLE


def console_out() -> Console:
    """Console для вывода в stdout (пользовательские данные, отчёты)."""
    return _CONSOLE_OUT