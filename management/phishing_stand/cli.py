"""CLI-точка входа приложения."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from phishing_stand import __version__
from phishing_stand.logger import console, console_out, get_logger, setup_logging

app = typer.Typer(
    name="phishing-stand",
    help="Автоматизация развёртывания стенда для проверки осведомлённости пользователей.",
    add_completion=True,
    no_args_is_help=True,
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

log = get_logger("cli")


# ============================================================================
# Callback для глобальных опций
# ============================================================================
def _version_callback(value: bool) -> None:
    if value:
        console_out.print(f"phishing-stand {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Подробный вывод (DEBUG)"),
    version: Optional[bool] = typer.Option(  # noqa: UP007
        None, "--version", callback=_version_callback, is_eager=True, help="Показать версию"
    ),
) -> None:
    setup_logging(verbose=verbose)


# ============================================================================
# Автообнаружение архива импорта
# ============================================================================
def _find_import_archive(directory: Path | None = None) -> Path | None:
    """Ищет в директории архив экспорта.

    Правила:
    - Если ровно один файл `phishing_stand_export_*.tar.gz` — возвращаем его.
    - Если несколько — возвращаем None (пользователь должен выбрать явно).
    - Поддерживаются также `.tar.gz.enc` (зашифрованные).
    """
    search_dir = directory or Path.cwd()
    if not search_dir.is_dir():
        return None

    candidates = sorted(
        p
        for p in search_dir.iterdir()
        if p.is_file()
        and (p.name.startswith("phishing_stand_export_"))
        and (p.name.endswith(".tar.gz") or p.name.endswith(".tar.gz.enc"))
    )

    if len(candidates) == 1:
        return candidates[0]
    return None


def _prompt_import_if_found(archive: Path) -> bool:
    """Спрашивает пользователя, хочет ли он импортировать найденный архив."""
    console().print()
    console().print(
        Panel(
            f"[bold cyan]Обнаружен архив экспорта:[/]\n"
            f"  [yellow]{archive.name}[/]\n"
            f"  Размер: [green]{archive.stat().st_size / 1024 / 1024:.1f} MB[/]",
            title="🔍 Автообнаружение импорта",
            border_style="cyan",
        )
    )
    return typer.confirm("Импортировать данные из этого архива вместо нового развёртывания?", default=True)


# ============================================================================
# Команда: deploy
# ============================================================================
@app.command(help="Развёртывание стенда. Автоматически подхватывает архив импорта, если он найден.")
def deploy(
    import_from: Optional[Path] = typer.Option(  # noqa: UP007
        None,
        "--import-from",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Явно указать архив для импорта вместо развёртывания с нуля",
    ),
    auto_import: bool = typer.Option(
        True,
        "--auto-import/--no-auto-import",
        help="Автоматически искать архив импорта в текущей директории",
    ),
    resume: bool = typer.Option(False, "--resume", help="Продолжить с прерванного шага"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Показать план без выполнения"),
    skip_import_confirm: bool = typer.Option(
        False, "--yes", "-y", help="Не спрашивать подтверждение при автообнаружении импорта"
    ),
) -> None:
    """Развёртывание стенда с опциональным импортом."""
    from phishing_stand.deploy import run_deploy, run_import_deploy

    # 1. Явный импорт через --import-from
    if import_from is not None:
        log.info(f"Запуск развёртывания с импортом из: {import_from}")
        run_import_deploy(archive_path=import_from, dry_run=dry_run)
        return

    # 2. Автообнаружение
    if auto_import:
        found = _find_import_archive()
        if found is not None:
            use_import = skip_import_confirm or _prompt_import_if_found(found)
            if use_import:
                log.info(f"Автообнаружен архив: {found}")
                run_import_deploy(archive_path=found, dry_run=dry_run)
                return
            log.info("Пользователь отказался от импорта, продолжаем обычное развёртывание")

    # 3. Обычное развёртывание
    run_deploy(resume=resume, dry_run=dry_run)


# ============================================================================
# Команда: export
# ============================================================================
@app.command(help="Экспорт данных стенда в архив.")
def export(
    output: Optional[Path] = typer.Option(  # noqa: UP007
        None, "--output", "-o", help="Путь для архива (по умолчанию — текущая директория)"
    ),
    encrypt: bool = typer.Option(False, "--encrypt", help="Зашифровать архив AES-256"),
    config_only: bool = typer.Option(
        False, "--config-only", help="Только конфигурация (без БД и сессий)"
    ),
) -> None:
    """Экспорт данных стенда."""
    from phishing_stand.export import run_export

    run_export(output_dir=output or Path.cwd(), encrypt=encrypt, config_only=config_only)


# ============================================================================
# Команда: import
# ============================================================================
@app.command(name="import", help="Импорт данных стенда из архива.")
def import_cmd(
    archive: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, help="Путь к архиву"),
    overwrite_env: bool = typer.Option(
        False, "--overwrite-env", help="Перезаписать существующий .env без вопроса"
    ),
    validate_only: bool = typer.Option(
        False, "--validate-only", help="Только проверить архив, не импортировать"
    ),
) -> None:
    """Импорт данных из архива."""
    from phishing_stand.import_ import run_import

    run_import(archive_path=archive, overwrite_env=overwrite_env, validate_only=validate_only)


# ============================================================================
# Команда: status
# ============================================================================
@app.command(help="Проверка состояния всех сервисов стенда.")
def status(
    as_json: bool = typer.Option(False, "--json", help="Вывод в формате JSON"),
) -> None:
    """Показать состояние стенда."""
    from phishing_stand.status import run_status

    run_status(as_json=as_json)


# ============================================================================
# Команда: config
# ============================================================================
config_app = typer.Typer(help="Управление конфигурацией (.env).")
app.add_typer(config_app, name="config")


@config_app.command(name="show")
def config_show() -> None:
    """Показать текущую конфигурацию."""
    from phishing_stand.config import Settings

    settings = Settings.from_env_file_or_none()
    if settings is None:
        console().print("[yellow]Файл .env не найден или невалиден[/]")
        raise typer.Exit(1)

    table = Table(title="Текущая конфигурация", show_header=True, header_style="bold cyan")
    table.add_column("Параметр", style="green")
    table.add_column("Значение", style="yellow")
    for field_name in settings.model_fields:
        table.add_row(field_name, str(getattr(settings, field_name)))
    console_out().print(table)


@config_app.command(name="validate")
def config_validate() -> None:
    """Проверить валидность .env."""
    from phishing_stand.config import Settings

    try:
        Settings.from_env_file()
        console().print("[success]✓ Конфигурация валидна[/]")
    except (FileNotFoundError, ValueError) as e:
        console().print(f"[error]✗ Ошибка валидации:[/]\n{e}")
        raise typer.Exit(1)


# ============================================================================
# Точка входа
# ============================================================================
def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console().print("\n[yellow]Прервано пользователем[/]")
        sys.exit(130)
    except (PermissionError, FileNotFoundError, RuntimeError, ValueError) as e:
        console().print(f"\n[error]Ошибка:[/] {e}")
        sys.exit(1)