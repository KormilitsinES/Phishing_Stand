# phishing_stand/deploy/steps/base.py
"""Абстрактный базовый класс для шага развёртывания."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from phishing_stand.config import Settings
    from phishing_stand.state import DeployState


class Step(ABC):
    """Базовый класс для шага развёртывания.

    Каждый шаг:
    - Имеет уникальное имя (используется в state для отслеживания).
    - Может зависеть от других шагов (depends_on).
    - Идемпотентен: повторный запуск не ломает систему.
    - Поддерживает rollback (опционально).
    - Может быть пропущен, если уже выполнен (resume-режим).
    """

    # ---------- Метаданные шага (переопределяются в наследниках) ----------
    name: ClassVar[str] = "base"
    description: ClassVar[str] = "Базовый шаг"
    depends_on: ClassVar[list[str]] = []
    requires_root: ClassVar[bool] = True

    def __init__(self, settings: "Settings", state: "DeployState") -> None:
        self.settings = settings
        self.state = state
        self.log: logging.Logger = logging.getLogger(f"phishing_stand.step.{self.name}")

    # ---------- Основной интерфейс ----------
    @abstractmethod
    def execute(self) -> bool:
        """Выполнить шаг.

        Returns:
            True — шаг успешно выполнен.
            False — шаг завершился с ошибкой (оркестратор остановится).

        Raises:
            Exception — любая ошибка будет перехвачена оркестратором
                        и записана в state как failed.
        """

    def rollback(self) -> None:
        """Откатить шаг (опционально). Вызывается при ошибке."""
        self.log.debug(f"Rollback not implemented for step '{self.name}'")

    def pre_check(self) -> bool:
        """Предварительная проверка: можно ли выполнять шаг.

        По умолчанию возвращает True. Переопределяется, если шаг
        требует специфических условий (например, наличие файла).
        """
        return True

    # ---------- Работа с состоянием ----------
    def is_completed(self) -> bool:
        """Проверить, был ли шаг уже выполнен."""
        return self.state.is_step_done(self.name)

    def mark_completed(self, message: str = "") -> None:
        self.state.mark_step_done(self.name, message=message)

    def mark_failed(self, message: str = "") -> None:
        self.state.mark_step_failed(self.name, message=message)

    def mark_skipped(self, message: str = "") -> None:
        self.state.mark_step_skipped(self.name, message=message)

    # ---------- Вспомогательные методы ----------
    def __repr__(self) -> str:
        return f"<Step:{self.name}>"