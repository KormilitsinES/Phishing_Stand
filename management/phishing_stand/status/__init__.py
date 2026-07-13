# phishing_stand/status/__init__.py
"""Проверка состояния стенда."""
from __future__ import annotations

from phishing_stand.logger import console, get_logger

log = get_logger("status")


def run_status(*, as_json: bool = False) -> None:
    log.info("Проверка состояния стенда")
    console().print("[yellow]ℹ Реализация status — на следующем шаге.[/]")