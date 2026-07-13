# phishing_stand/deploy/__init__.py
"""Команды развёртывания."""
from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path

from phishing_stand.config import Settings
from phishing_stand.deploy.orchestrator import DeployOrchestrator
from phishing_stand.deploy.steps import STEPS_REGISTRY
from phishing_stand.logger import console, get_logger
from phishing_stand.state import DeployState
from phishing_stand.utils import ensure_dir, safe_copy

log = get_logger("deploy")


def run_deploy(*, resume: bool = False, dry_run: bool = False) -> None:
    """Обычное развёртывание стенда (шаги из STEPS_REGISTRY)."""
    log.info(f"Запуск развёртывания (resume={resume}, dry_run={dry_run})")

    # Загружаем или создаём конфигурацию
    settings = Settings.from_env_file_or_none()
    if settings is None:
        if dry_run:
            log.warning("Файл .env не найден, использую дефолты для dry-run")
            settings = _make_dummy_settings()
        else:
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
    4. Запускаем оставшиеся шаги (docker_compose, finalize).
    """
    log.info(f"Развёртывание с импортом из: {archive_path}")

    if dry_run:
        console().print(f"[yellow]DRY-RUN: Импорт из {archive_path}[/]")
        return

    # 1. Распаковываем архив
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        log.info("Распаковываю архив...")

        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(tmp_path)
        except Exception as e:
            log.error(f"Не удалось распаковать архив: {e}")
            raise SystemExit(1)

        # 2. Читаем метаданные
        metadata_file = tmp_path / "export_metadata.json"
        metadata = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            log.info(f"Архив создан: {metadata.get('export_timestamp', 'unknown')}")

        # 3. Восстанавливаем файлы
        _restore_env(tmp_path)
        _restore_certs(tmp_path)
        _restore_gophish_db(tmp_path)
        _restore_evilginx(tmp_path)
        _restore_dkim(tmp_path)

    # 4. Загружаем конфигурацию из восстановленного .env
    settings = Settings.from_env_file()
    log.success(f"Конфигурация загружена: {settings.BASE_DOMAIN}")

    # 5. Запускаем только необходимые шаги (пропускаем те, что покрыты импортом)
    state = DeployState()

    # Отмечаем шаги, которые не нужно выполнять
    state.mark_step_done("system_update", "skipped via import")
    state.mark_step_done("install_docker", "skipped via import")
    state.mark_step_done("generate_env", "restored from archive")
    state.mark_step_done("certbot", "restored from archive")
    state.mark_step_done("dkim", "restored from archive")

    # Инициализируем только оставшиеся шаги
    steps_to_run = [DockerComposeStep(settings, state), FinalizeStep(settings, state)]

    # Запускаем оркестратор
    orchestrator = DeployOrchestrator(steps=steps_to_run, settings=settings, state=state)
    success = orchestrator.run(resume=False, dry_run=False)

    if not success:
        raise SystemExit(1)


# ---------- Вспомогательные функции для импорта ----------

def _restore_env(tmp_path: Path) -> None:
    """Восстанавливаем .env из архива."""
    src = tmp_path / ".env"
    dst = Path(".env")
    if src.exists():
        safe_copy(src, dst)
        log.success("✓ .env восстановлен")
    else:
        log.warning(".env не найден в архиве")


def _restore_certs(tmp_path: Path) -> None:
    """Восстанавливаем сертификаты."""
    src = tmp_path / "certs"
    dst = Path("certs")
    if src.exists():
        safe_copy(src, dst)
        log.success("✓ SSL-сертификаты восстановлены")
    else:
        log.warning("certs/ не найдены в архиве")


def _restore_gophish_db(tmp_path: Path) -> None:
    """Восстанавливаем БД Gophish."""
    src = tmp_path / "gophish" / "gophish.db"
    dst = Path("gophish/gophish.db")
    if src.exists():
        ensure_dir(dst.parent)
        safe_copy(src, dst)
        dst.chmod(0o666)
        log.success("✓ gophish.db восстановлена")
    else:
        log.warning("gophish/gophish.db не найдена в архиве")


def _restore_evilginx(tmp_path: Path) -> None:
    """Восстанавливаем данные Evilginx2."""
    src_base = tmp_path / "evilginx2"
    if not src_base.exists():
        log.warning("evilginx2/ не найден в архиве")
        return

    # Phishlets
    src_phishlets = src_base / "phishlets"
    dst_phishlets = Path("evilginx2/phishlets")
    if src_phishlets.exists():
        safe_copy(src_phishlets, dst_phishlets)
        log.success("✓ evilginx2/phishlets восстановлены")

    # Data
    src_data = src_base / "data"
    dst_data = Path("evilginx2/data")
    if src_data.exists():
        safe_copy(src_data, dst_data)
        log.success("✓ evilginx2/data восстановлена")


def _restore_dkim(tmp_path: Path) -> None:
    """Восстанавливаем DKIM-ключи."""
    src = tmp_path / "postfix" / "dkim"
    dst = Path("postfix/dkim")
    if src.exists():
        ensure_dir(dst)
        safe_copy(src, dst)
        log.success("✓ DKIM-ключи восстановлены")
    else:
        log.warning("postfix/dkim/ не найдены в архиве")


# ---------- Вспомогательные функции ----------

def _make_empty_settings() -> Settings:
    """Пустая конфигурация — будет заполнена GenerateEnvStep."""
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