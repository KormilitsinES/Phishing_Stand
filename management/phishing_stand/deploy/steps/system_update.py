# phishing_stand/deploy/steps/system_update.py
"""Обновление системных пакетов и установка базовых утилит."""
from __future__ import annotations

from phishing_stand.deploy.steps.base import Step
from phishing_stand.utils import run


class SystemUpdateStep(Step):
    name = "system_update"
    description = "Обновление системных пакетов"
    depends_on: list[str] = []
    requires_root = True

    # Пакеты, которые точно нужны для работы стенда
    REQUIRED_PACKAGES = [
        "curl",
        "wget",
        "git",
        "ca-certificates",
        "gnupg",
        "lsb-release",
        "python3",
        "python3-venv",
        "python3-pip",
    ]

    def execute(self) -> bool:
        self.log.info("Обновляю списки пакетов...")
        r = run(["apt-get", "update", "-qq"], check=False)
        if not r.ok:
            self.log.error(f"apt-get update завершился с кодом {r.returncode}")
            return False

        self.log.info(f"Устанавливаю базовые пакеты: {', '.join(self.REQUIRED_PACKAGES)}")
        r = run(
            ["apt-get", "install", "-y", "-qq", *self.REQUIRED_PACKAGES],
            check=False,
            timeout=600,
        )
        if not r.ok:
            self.log.error(f"Не удалось установить пакеты: {r.stderr}")
            return False

        self.log.success("Системные пакеты обновлены")
        return True

    def rollback(self) -> None:
        # Откат для apt-get не делаем — это безопасно и идемпотентно
        self.log.debug("Rollback не требуется для system_update")