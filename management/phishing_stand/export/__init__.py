# phishing_stand/export/__init__.py
"""Экспорт данных стенда."""
from __future__ import annotations

from pathlib import Path

from phishing_stand.logger import console, get_logger

log = get_logger("export")


def run_export(*, output_dir: Path, encrypt: bool = False, config_only: bool = False) -> None:
    log.info(f"Экспорт в {output_dir} (encrypt={encrypt}, config_only={config_only})")
    console().print("[yellow]ℹ Реализация экспорта — на следующем шаге.[/]")