"""Интерактивная генерация .env файла."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

import typer
from rich.panel import Panel

from phishing_stand.config import Settings
from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import console
from phishing_stand.utils import run

ENV_FILE: Final[Path] = Path(".env")

# Шаблон .env
ENV_TEMPLATE: Final[str] = """# Конфигурация стенда Phishing Stand
# Сгенерировано автоматически — можно редактировать вручную

# --- Домены ---
BASE_DOMAIN={base_domain}
TRACK_DOMAIN={track_domain}
EVIL_DOMAIN={evil_domain}
MX_DOMAIN={mx_domain}

# --- Администратор ---
ADMIN_EMAIL={admin_email}

# --- Сеть ---
VPS_IP={vps_ip}

# --- Имена контейнеров (не менять без необходимости) ---
GOPHISH_BACKEND=gophish
POSTFIX_BACKEND=postfix
EVILGINX_BACKEND=evilginx2
"""


class GenerateEnvStep(Step):
    name = "generate_env"
    description = "Генерация конфигурации (.env)"
    depends_on = ["install_docker"]
    requires_root = False

    def execute(self) -> bool:
        # 1. Если .env уже существует — используем его
        if ENV_FILE.exists():
            self.log.info(f"Файл {ENV_FILE} уже существует, использую его")
            try:
                self.settings = Settings.from_env_file(ENV_FILE)
                self.log.success(f"Конфигурация загружена: {self.settings.BASE_DOMAIN}")
                return True
            except (ValueError, FileNotFoundError) as e:
                self.log.warning(f"Текущий .env невалиден: {e}")
                if not typer.confirm("Пересоздать .env?", default=False):
                    return False

        # 2. Проверка на неинтерактивный режим (чтобы не зависать в CI/CD или при pipe)
        if not sys.stdin.isatty():
            self.log.error("Неинтерактивный режим: файл .env не найден, а ввод с клавиатуры невозможен.")
            self.log.error("Создайте файл .env вручную или запустите скрипт в интерактивном терминале.")
            return False

        # 3. Интерактивный опрос
        console().print(
            Panel(
                "[bold]Настройка конфигурации стенда[/]\n"
                "Вам потребуется указать домены и IP-адрес сервера.\n"
                "Все значения можно будет изменить позже в файле .env",
                border_style="cyan",
            )
        )

        data = self._interactive_prompt()

        # 4. Валидация через Pydantic
        try:
            self.settings = Settings.model_validate(data)
        except Exception as e:
            self.log.error(f"Ошибка валидации конфигурации:\n{e}")
            return False

        # 5. Запись .env
        content = ENV_TEMPLATE.format(**data)
        ENV_FILE.write_text(content, encoding="utf-8")
        ENV_FILE.chmod(0o600)

        self.log.success(f"Конфигурация сохранена в {ENV_FILE}")
        return True

    def _interactive_prompt(self) -> dict[str, str]:
        """Интерактивно собирает данные у пользователя."""
        data: dict[str, str] = {}

        data["base_domain"] = self._prompt_domain(
            "Базовый домен (например, example.com)",
            default=self.settings.BASE_DOMAIN if hasattr(self, "settings") else "",
        )

        base = data["base_domain"]
        data["track_domain"] = self._prompt_domain("Домен для трекинга Gophish", default=f"t.{base}")
        data["evil_domain"] = self._prompt_domain("Домен для Evilginx2", default=f"e.{base}")
        data["mx_domain"] = self._prompt_domain("Домен для почтового шлюза (MX)", default=f"mail.{base}")
        data["admin_email"] = self._prompt_email("Email администратора", default=f"admin@{base}")
        data["vps_ip"] = self._prompt_ip("Публичный IP-адрес сервера", default=self._detect_public_ip())

        return data

    def _prompt_domain(self, message: str, default: str = "") -> str:
        pattern = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$")
        while True:
            value = typer.prompt(message, default=default or None).strip().lower()
            if pattern.match(value):
                return value
            console().print(f"[red]Некорректный домен:[/] {value}")

    def _prompt_email(self, message: str, default: str = "") -> str:
        pattern = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
        while True:
            value = typer.prompt(message, default=default or None).strip().lower()
            if pattern.match(value):
                return value
            console().print(f"[red]Некорректный email:[/] {value}")

    def _prompt_ip(self, message: str, default: str = "") -> str:
        pattern = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$")
        while True:
            value = typer.prompt(message, default=default or None).strip()
            if pattern.match(value):
                return value
            console().print(f"[red]Некорректный IPv4:[/] {value}")

    def _detect_public_ip(self) -> str:
        """Пытается определить публичный IP автоматически (с жёсткими таймаутами)."""
        for url in ("https://api.ipify.org", "https://ifconfig.me", "https://icanhazip.com"):
            try:
                # Явный таймаут 5 секунд на уровне subprocess + 3 секунды на уровне curl
                r = run(["curl", "-fsSL", "--max-time", "3", url], check=False, timeout=5)
                if r.ok and r.stdout.strip():
                    ip = r.stdout.strip()
                    # Дополнительная проверка, что вернулось именно число, а не ошибка провайдера
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                        self.log.debug(f"Определён п