# phishing_stand/deploy/__init__.py
"""Команды развёртывания."""
from __future__ import annotations

from pathlib import Path

from phishing_stand.logger import console, get_logger

log = get_logger("deploy")


def run_deploy(*, resume: bool = False, dry_run: bool = False) -> None:
    """Обычное развёртывание стенда (шаги 1..N)."""
    log.info(f"Запуск развёртывания (resume={resume}, dry_run={dry_run})")
    console().print("[yellow]ℹ Реализация шагов развёртывания — на следующем шаге.[/]")


def run_import_deploy(*, archive_path: Path, dry_run: bool = False) -> None:
    """Развёртывание с импортом данных из архива."""
    log.info(f"Развёртывание с импортом из: {archive_path} (dry_run={dry_run})")
    console().print("[yellow]ℹ Реализация импорта при deploy — на следующем шаге.[/]")