# phishing_stand/deploy/steps/install_docker.py
"""Установка Docker Engine и Docker Compose."""
from __future__ import annotations

import shutil

from phishing_stand.deploy.steps.base import Step
from phishing_stand.utils import run


class InstallDockerStep(Step):
    name = "install_docker"
    description = "Установка Docker Engine"
    depends_on = ["system_update"]
    requires_root = True

    def pre_check(self) -> bool:
        """Проверяем, что apt-get доступен (для Debian/Ubuntu)."""
        return shutil.which("apt-get") is not None

    def execute(self) -> bool:
        # 1. Если Docker уже установлен — проверяем версию
        if self._is_docker_installed():
            version = self._get_docker_version()
            self.log.success(f"Docker уже установлен: {version}")
            # Убеждаемся, что compose тоже есть
            if not self._is_compose_available():
                self.log.info("Docker Compose не найден, устанавливаю...")
                if not self._install_compose_plugin():
                    return False
            return True

        # 2. Установка Docker через официальный скрипт
        self.log.info("Устанавливаю Docker через get.docker.com...")
        r = run(
            "curl -fsSL https://get.docker.com | sh",
            check=False,
            timeout=600,
        )
        if not r.ok:
            self.log.error(f"Установка Docker завершилась с ошибкой:\n{r.stderr}")
            return False

        # 3. Запускаем и включаем в автозагрузку
        self.log.info("Запускаю Docker daemon...")
        run(["systemctl", "enable", "--now", "docker"], check=False)

        # 4. Проверяем, что Docker работает
        if not self._is_docker_running():
            self.log.error("Docker установлен, но daemon не запускается")
            return False

        version = self._get_docker_version()
        self.log.success(f"Docker успешно установлен: {version}")
        return True

    # ---------- Вспомогательные методы ----------
    def _is_docker_installed(self) -> bool:
        return shutil.which("docker") is not None

    def _is_docker_running(self) -> bool:
        r = run(["docker", "info"], check=False, timeout=10)
        return r.ok

    def _get_docker_version(self) -> str:
        r = run(["docker", "--version"], check=False, timeout=5)
        return r.stdout.strip() if r.ok else "unknown"

    def _is_compose_available(self) -> bool:
        r = run(["docker", "compose", "version"], check=False, timeout=5)
        return r.ok

    def _install_compose_plugin(self) -> bool:
        r = run(
            ["apt-get", "install", "-y", "-qq", "docker-compose-plugin"],
            check=False,
            timeout=300,
        )
        if r.ok:
            self.log.success("Docker Compose plugin установлен")
            return True
        self.log.error(f"Не удалось установить docker-compose-plugin: {r.stderr}")
        return False