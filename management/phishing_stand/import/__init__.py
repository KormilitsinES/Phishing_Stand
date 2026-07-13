# phishing_stand/import_/__init__.py
"""Импорт данных стенда."""
from __future__ import annotations

from pathlib import Path

from phishing_stand.logger import console, get_logger

log = get_logger("import")


def run_import(*, archive_path: Path, overwrite_env: bool = False, validate_only: bool = False) -> None:
    log.info(f"Импорт из {archive_path} (validate_only={validate_only})")
    console().print("[yellow]ℹ Реализация импорта — на следующем шаге.[/]")