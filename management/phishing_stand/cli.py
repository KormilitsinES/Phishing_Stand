"""CLI-точка входа приложения."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from phishing_stand import __version__
from phishing_stand.logger import get_logger, setup_logging

app = typer.Typer(
    name="phishing-stand",
    help="Автоматизация развёртывания стенда для проверки осведомлённости пользователей.",
    add_completion=True,
    no_args_is_help=True,
)

log = get_logger("cli")

def _version_callback(value: bool) -> None:
    if value:
        print(f"phishing-stand {__version__}")
        raise typer.Exit()

@app.callback()
def _main(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Подробный вывод (DEBUG)"),
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="Показать версию"
    ),
) -> None:
    setup_logging(verbose=verbose)

def _find_import_archive(directory: Path | None = None) -> Path | None:
    search_dir = directory or Path.cwd()
    if not search_dir.is_dir():
        return None
    candidates = sorted(
        p for p in search_dir.iterdir()
        if p.is_file() and p.name.startswith("phishing_stand_export_") and (p.name.endswith(".tar.gz") or p.name.endswith(".tar.gz.enc"))
    )
    return candidates[0] if len(candidates) == 1 else None

def _prompt_import_if_found(archive: Path) -> bool:
    print("\n" + "="*60)
    print(" ОБНАРУЖЕН АРХИВ ЭКСПОРТА")
    print(f" Файл:  {archive.name}")
    print(f" Размер: {archive.stat().st_size / 1024 / 1024:.1f} MB")
    print("="*60)
    return input("Импортировать данные из этого архива вместо нового развёртывания? (y/N): ").strip().lower() in ('y', 'yes')

@app.command(help="Развёртывание стенда. Автоматически подхватывает архив импорта, если он найден.")
def deploy(
    import_from: Optional[Path] = typer.Option(None, "--import-from", "-i", exists=True, file_okay=True, dir_okay=False, help="Явно указать архив для импорта"),
    auto_import: bool = typer.Option(True, "--auto-import/--no-auto-import", help="Автоматически искать архив импорта"),
    resume: bool = typer.Option(False, "--resume", help="Продолжить с прерванного шага"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Показать план без выполнения"),
    skip_import_confirm: bool = typer.Option(False, "--yes", "-y", help="Не спрашивать подтверждение при автообнаружении"),
) -> None:
    from phishing_stand.deploy import run_deploy, run_import_deploy

    if import_from is not None:
        log.info(f"Запуск развёртывания с импортом из: {import_from}")
        run_import_deploy(archive_path=import_from, dry_run=dry_run)
        return

    if auto_import:
        found = _find_import_archive()
        if found is not None:
            use_import = skip_import_confirm or _prompt_import_if_found(found)
            if use_import:
                log.info(f"Автообнаружен архив: {found}")
                run_import_deploy(archive_path=found, dry_run=dry_run)
                return
            log.info("Пользователь отказался от импорта, продолжаем обычное развёртывание")

    run_deploy(resume=resume, dry_run=dry_run)

@app.command(help="Экспорт данных стенда в архив.")
def export_cmd(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Путь для архива"),
    encrypt: bool = typer.Option(False, "--encrypt", help="Зашифровать архив AES-256"),
    config_only: bool = typer.Option(False, "--config-only", help="Только конфигурация (без БД и сессий)"),
) -> None:
    from phishing_stand.export import run_export
    run_export(output_dir=output or Path.cwd(), encrypt=encrypt, config_only=config_only)

@app.command(name="import", help="Импорт данных стенда из архива.")
def import_cmd(
    archive: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, help="Путь к архиву"),
    overwrite_env: bool = typer.Option(False, "--overwrite-env", help="Перезаписать существующий .env без вопроса"),
    validate_only: bool = typer.Option(False, "--validate-only", help="Только проверить архив, не импортировать"),
) -> None:
    from phishing_stand.import_ import run_import
    run_import(archive_path=archive, overwrite_env=overwrite_env, validate_only=validate_only)

@app.command(help="Проверка состояния всех сервисов стенда.")
def status_cmd(as_json: bool = typer.Option(False, "--json", help="Вывод в формате JSON")) -> None:
    from phishing_stand.status import run_status
    run_status(as_json=as_json)

config_app = typer.Typer(help="Управление конфигурацией (.env).")
app.add_typer(config_app, name="config")

@config_app.command(name="show")
def config_show() -> None:
    from phishing_stand.config import Settings
    settings = Settings.from_env_file_or_none()
    if settings is None:
        print("Файл .env не найден или невалиден")
        raise typer.Exit(1)
    print("\nТекущая конфигурация:")
    print("-" * 40)
    for field_name in settings.model_fields:
        print(f"{field_name:<20} : {getattr(settings, field_name)}")
    print("-" * 40)

@config_app.command(name="validate")
def config_validate() -> None:
    from phishing_stand.config import Settings
    try:
        Settings.from_env_file()
        print("✓ Конфигурация валидна")
    except (FileNotFoundError, ValueError) as e:
        print(f"✗ Ошибка валидации:\n{e}")
        raise typer.Exit(1)

def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        sys.exit(130)
    except (PermissionError, FileNotFoundError, RuntimeError, ValueError) as e:
        print(f"\nОшибка: {e}")
        sys.exit(1)