"""Генерация .env файла."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

from phishing_stand.config import Settings
from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import get_logger
from phishing_stand.utils import run

ENV_FILE: Final[Path] = Path(".env")
log = get_logger("generate_env")

ENV_TEMPLATE: Final[str] = """# Конфигурация стенда Phishing Stand
BASE_DOMAIN={base_domain}
TRACK_DOMAIN={track_domain}
EVIL_DOMAIN={evil_domain}
MX_DOMAIN={mx_domain}
ADMIN_EMAIL={admin_email}
VPS_IP={vps_ip}
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
        # 1. Если файл есть, просто читаем и валидируем его. Это самый частый сценарий.
        if ENV_FILE.exists():
            log.info("Файл .env найден, проверяю его валидность...")
            try:
                self.settings = Settings.from_env_file(ENV_FILE)
                log.success(f"Конфигурация валидна: {self.settings.BASE_DOMAIN}")
                return True
            except (ValueError, FileNotFoundError) as e:
                log.error(f"Файл .env невалиден: {e}")
                print("Удалите или исправьте файл .env и запустите скрипт снова.")
                return False

        # 2. Если файла нет, проверяем, можем ли мы спросить пользователя
        if not sys.stdin.isatty():
            log.error("Неинтерактивный режим: файл .env не найден.")
            log.error("Создайте файл .env вручную перед запуском.")
            return False

        print("\n--- Настройка конфигурации стенда ---")
        print("Файл .env не найден. Ответьте на несколько вопросов.")
        print("(Нажмите Enter, чтобы принять значение по умолчанию)\n")

        data = self._interactive_prompt()

        try:
            self.settings = Settings.model_validate(data)
        except Exception as e:
            log.error(f"Ошибка валидации: {e}")
            return False

        ENV_FILE.write_text(ENV_TEMPLATE.format(**data), encoding="utf-8")
        ENV_FILE.chmod(0o600)
        log.success(f"Конфигурация сохранена в {ENV_FILE}")
        return True

    def _interactive_prompt(self) -> dict[str, str]:
        data: dict[str, str] = {}

        base_default = getattr(self, "settings", None)
        base_default = base_default.BASE_DOMAIN if base_default else ""

        data["base_domain"] = self._prompt("Базовый домен (например, example.com)", base_default, self._is_valid_domain)
        base = data["base_domain"]

        data["track_domain"] = self._prompt("Домен для трекинга Gophish", f"t.{base}", self._is_valid_domain)
        data["evil_domain"] = self._prompt("Домен для Evilginx2", f"e.{base}", self._is_valid_domain)
        data["mx_domain"] = self._prompt("Домен для почтового шлюза (MX)", f"mail.{base}", self._is_valid_domain)
        data["admin_email"] = self._prompt("Email администратора", f"admin@{base}", self._is_valid_email)
        data["vps_ip"] = self._prompt("Публичный IP-адрес сервера", self._detect_public_ip(), self._is_valid_ip)

        return data

    def _prompt(self, message: str, default: str, validator) -> str:
        default_str = f" [{default}]" if default else ""
        while True:
            try:
                value = input(f"{message}{default_str}: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nПрервано пользователем.")
                sys.exit(1)

            if not value and default:
                value = default

            if validator(value):
                return value.lower() if "domain" in message or "email" in message else value
            print("  [Ошибка] Некорректное значение. Попробуйте снова.")

    def _is_valid_domain(self, v: str) -> bool:
        return bool(re.match(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,}$", v))

    def _is_valid_email(self, v: str) -> bool:
        return bool(re.match(r"^[\w.+-]+@[\w-]+\.[\w.-]+$", v))

    def _is_valid_ip(self, v: str) -> bool:
        return bool(re.match(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$", v))

    def _detect_public_ip(self) -> str:
        for url in ("https://api.ipify.org", "https://ifconfig.me"):
            try:
                r = run(["curl", "-fsSL", "--max-time", "3", url], check=False, timeout=5)
                if r.ok and r.stdout.strip():
                    ip = r.stdout.strip()
                    if self._is_valid_ip(ip):
                        return ip
            except Exception:
                continue
        return ""