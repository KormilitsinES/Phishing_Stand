"""Команды развёртывания."""
from __future__ import annotations

import json
import tarfile
import tempfile
from pathlib import Path

from phishing_stand.config import Settings
from phishing_stand.deploy.orchestrator import DeployOrchestrator
from phishing_stand.deploy.steps import STEPS_REGISTRY
from phishing_stand.deploy.steps.docker_compose import DockerComposeStep
from phishing_stand.deploy.steps.finalize import FinalizeStep
from phishing_stand.logger import get_logger
from phishing_stand.state import DeployState
from phishing_stand.utils import ensure_dir, safe_copy

log = get_logger("deploy")


def run_deploy(*, resume: bool = False, dry_run: bool = False) -> None:
    log.info(f"Запуск развёртывания (resume={resume}, dry_run={dry_run})")
    settings = Settings.from_env_file_or_none()
    if settings is None:
        if dry_run:
            log.warning("Файл .env не найден, использую дефолты для dry-run")
            settings = _make_dummy_settings()
        else:
            settings = _make_empty_settings()

    state = DeployState()
    steps = [step_cls(settings, state) for step_cls in STEPS_REGISTRY]
    orchestrator = DeployOrchestrator(steps=steps, settings=settings, state=state)

    if not orchestrator.run(resume=resume, dry_run=dry_run):
        raise SystemExit(1)


def run_import_deploy(*, archive_path: Path, dry_run: bool = False) -> None:
    log.info(f"Развёртывание с импортом из: {archive_path}")
    if dry_run:
        print(f"[DRY-RUN] Импорт из {archive_path}")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        log.info("Распаковываю архив...")
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(tmp_path)
        except Exception as e:
            log.error(f"Не удалось распаковать архив: {e}")
            raise SystemExit(1)

        _restore_env(tmp_path)
        _restore_certs(tmp_path)
        _restore_gophish_db(tmp_path)
        _restore_evilginx(tmp_path)
        _restore_dkim(tmp_path)

    settings = Settings.from_env_file()
    log.success(f"Конфигурация загружена: {settings.BASE_DOMAIN}")

    state = DeployState()
    state.mark_step_done("system_update", "skipped via import")
    state.mark_step_done("install_docker", "skipped via import")
    state.mark_step_done("generate_env", "restored from archive")
    state.mark_step_done("certbot", "restored from archive")
    state.mark_step_done("dkim", "restored from archive")

    steps_to_run = [