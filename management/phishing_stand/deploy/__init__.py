# phishing_stand/deploy/__init__.py
"""Команды развёртывания."""
from __future__ import annotations

from pathlib import Path

from phishing_stand.config import Settings
from phishing_stand.deploy.orchestrator import DeployOrchestrator
from phishing_stand.deploy.steps import STEPS_REGISTRY
from phishing_stand.logger import console, get_logger
from phishing_stand.state import DeployState

log = get_logger("deploy")


def run_deploy(*, resume: bool = False, dry_run: bool = False) -> None:
    """Обычное развёртывание стенда (шаги из STEPS_REGISTRY)."""
    log.info(f"Запуск развёртывания (resume={resume}, dry_run={dry_run})")

    # Загружаем или создаём конфигурацию
    settings = Settings.from_env_file_or_none()
    if settings is None:
        if dry_run:
            # Для dry-run используем заглушку
            log.warning("Файл .env не найден, использую дефолты для dry-run")
            settings = _make_dummy_settings()
        else:
            # GenerateEnvStep создаст .env интерактивно
            settings = _make_empty_settings()

    # Инициализируем шаги
    state = DeployState()
    steps = [step_cls(settings, state) for step_cls in STEPS_REGISTRY]

    # Запускаем оркестратор
    orchestrator = DeployOrchestrator(steps=steps, settings=settings, state=state)
    success = orchestrator.run(resume=resume, dry_run=dry_run)

    if not success:
        raise SystemExit(1)


def run_import_deploy(*, archive_path: Path, dry_run: bool = False) -> None:
    """Развёртывание с импортом данных из архива.

    Логика:
    1. Распаковываем архив во временную директорию.
    2. Восстанавливаем .env, сертификаты, БД, DKIM и т.д.
    3. Пропускаем шаги, которые уже покрыты импортом.
    4. Запускаем контейнеры.
    """
    log.info(f"Развёртывание с импортом из: {archive_path} (dry_run={dry_run})")
    console().print(
        "[yellow]ℹ Реализация импорта при deploy — на следующем шаге.[/]\n"
        f"    Архив: [cyan]{archive_path}[/]"
    )


# ---------- Вспомогательные функции ----------

def _make_empty_settings() -> Settings:
    """Пустая конфигурация — будет заполнена GenerateEnvStep."""
    # Возвращаем объект с пустыми строками; валидация произойдёт в шаге
    return Settings.model_construct(
        BASE_DOMAIN="",
        TRACK_DOMAIN="",
        EVIL_DOMAIN="",
        MX_DOMAIN="",
        ADMIN_EMAIL="",
        VPS_IP="",
    )


def _make_dummy_settings() -> Settings:
    """Заглушка для dry-run."""
    return Settings.model_construct(
        BASE_DOMAIN="example.com",
        TRACK_DOMAIN="t.example.com",
        EVIL_DOMAIN="e.example.com",
        MX_DOMAIN="mail.example.com",
        ADMIN_EMAIL="admin@example.com",
        VPS_IP="127.0.0.1",
    )