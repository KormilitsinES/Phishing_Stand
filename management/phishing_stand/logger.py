"""Простое и надёжное текстовое логирование."""
from __future__ import annotations

import logging
import sys

# Добавляем уровень SUCCESS (между INFO и WARNING)
logging.addLevelName(25, "SUCCESS")

class _SuccessLogger(logging.Logger):
    def success(self, msg: str, *args, **kwargs) -> None:
        if self.isEnabledFor(25):
            self._log(25, msg, args, **kwargs)

logging.setLoggerClass(_SuccessLogger)

def setup_logging(verbose: bool = False) -> None:
    """Инициализирует простое текстовое логирование."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

def get_logger(name: str | None = None) -> logging.Logger:
    """Возвращает логгер."""
    prefix = "phishing_stand"
    full_name = f"{prefix}.{name}" if name else prefix
    return logging.getLogger(full_name)