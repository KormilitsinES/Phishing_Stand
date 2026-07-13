# phishing_stand/deploy/orchestrator.py
"""Оркестратор: управляет порядком выполнения шагов."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from phishing_stand.config import Settings
from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import console, get_logger
from phishing_stand.state import DeployState
from phishing_stand.utils import require_root

log = get_logger("orchestrator")

BANNER: Final[str] = r"""
 ____  _     _     _       _     _   ____             _        _ _
|  _ \| |__ (_)___| |__   (_)___| |_|  _ \ ___  ___| |_ __ _| | |
| |_) | '_ \| / __| '_ \  | / __| __| |_) / _ \/ __| __/ _` | | |
|  __/| | | | \__ \ | | | | \__ \ |_|  _ <  __/ (__| || (_| | | |
|_|   |_| |_|_|___/_| |_| |_|___/\__|_| \_\___|\___|\__\__,_|_|_|
"""


class DeployOrchestrator:
    """Управляет последовательностью шагов развёртывания."""

    def __init__(
        self,
        steps: list[Step],
        settings: Settings,
        state: DeployState | None = None,
    ) -> None:
        self._steps = steps
        self._settings = settings
        self._state = state or DeployState()
        self._state.load()

    # ---------- Публичный интерфейс ----------
    def run(
        self,
        *,
        resume: bool = False,
        dry_run: bool = False,
    ) -> bool:
        """Запустить развёртывание.

        Args:
            resume: Продолжить с прерванного шага (пропустить уже выполненные).
            dry_run: Только показать план, не выполнять.

        Returns:
            True — все шаги выполнены успешно.
            False — один из шагов завершился с ошибкой.
        """
        self._print_banner()
        self._validate_dependencies()

        if not dry_run:
            self._check_root()

        self._state.mark_started()

        # Основной цикл
        with self._make_progress() as progress:
            task = progress.add_task("Развёртывание", total=len(self._steps))

            for step in self._steps:
                progress.update(task, description=f"[cyan]{step.description}[/]")

                # 1. Пропуск уже выполненных шагов (resume)
                if resume and step.is_completed():
                    log.info(f"⏭ Пропускаю завершённый шаг: [bold]{step.name}[/]")
                    progress.advance(task)
                    continue

                # 2. Предварительная проверка
                if not step.pre_check():
                    log.warning(f"⚠ Предварительная проверка не пройдена: {step.name}")
                    step.mark_skipped(message="pre_check failed")
                    progress.advance(task)
                    continue

                # 3. Dry-run: только показать план
                if dry_run:
                    log.info(f"[DRY-RUN] ▶ {step.name}: {step.description}")
                    progress.advance(task)
                    continue

                # 4. Выполнение шага
                success = self._execute_step(step, progress)
                if not success:
                    self._print_failure_report()
                    return False

                progress.advance(task)

        # Успех
        self._state.mark_finished()
        self._print_success_report()
        return True

    def plan(self) -> list[dict[str, str]]:
        """Вернуть план развёртывания (для dry-run и отладки)."""
        return [
            {
                "name": step.name,
                "description": step.description,
                "status": "done" if step.is_completed() else "pending",
                "depends_on": ",".join(step.depends_on) or "-",
            }
            for step in self._steps
        ]

    # ---------- Внутренние методы ----------
    def _execute_step(self, step: Step, progress: Progress) -> bool:
        """Выполнить один шаг с обработкой ошибок."""
        log.info(f"▶ [bold]{step.description}[/]  [dim]({step.name})[/]")
        try:
            success = step.execute()
            if success:
                step.mark_completed(message="ok")
                log.success(f"✓ {step.name} завершён")
                return True
            else:
                step.mark_failed(message="returned False")
                log.error(f"✗ {step.name} завершился с ошибкой")
                return False
        except Exception as e:
            step.mark_failed(message=str(e))
            log.exception(f"✗ Исключение в шаге {step.name}: {e}")
            try:
                step.rollback()
            except Exception as rb:
                log.error(f"✗ Rollback также завершился с ошибкой: {rb}")
            return False

    def _check_root(self) -> None:
        """Проверить, что есть шаги, требующие root, и что мы под root."""
        needs_root = any(s.requires_root for s in self._steps if not s.is_completed())
        if needs_root:
            require_root()

    def _validate_dependencies(self) -> None:
        """Проверить, что зависимости между шагами корректны."""
        names = {s.name for s in self._steps}
        for step in self._steps:
            for dep in step.depends_on:
                if dep not in names:
                    raise ValueError(
                        f"Шаг '{step.name}' зависит от несуществующего шага '{dep}'"
                    )

    def _make_progress(self) -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console(),
            transient=False,
        )

    def _print_banner(self) -> None:
        console().print(f"[bold cyan]{BANNER}[/]")
        console().print(
            Panel(
                f"[bold]Начало развёртывания[/]\n"
                f"Время: [yellow]{datetime.now():%Y-%m-%d %H:%M:%S}[/]\n"
                f"Шагов: [green]{len(self._steps)}[/]\n"
                f"Домен: [cyan]{self._settings.BASE_DOMAIN}[/]",
                border_style="cyan",
            )
        )

    def _print_success_report(self) -> None:
        table = Table(title="✓ Развёртывание завершено успешно", show_header=True)
        table.add_column("Шаг", style="green")
        table.add_column("Статус", style="cyan")
        table.add_column("Время", style="yellow")
        for step in self._steps:
            rec = self._state.steps.get(step.name)
            table.add_row(
                step.name,
                rec.status if rec else "—",
                rec.timestamp if rec else "—",
            )
        console().print(table)

    def _print_failure_report(self) -> None:
        console().print()
        console().print(
            Panel(
                "[bold red]✗ Развёртывание прервано из-за ошибки[/]\n"
                "Вы можете:\n"
                "  • Исправить проблему и запустить: [cyan]phishing-stand deploy --resume[/]\n"
                "  • Посмотреть состояние: [cyan]phishing-stand status[/]",
                title="Ошибка",
                border_style="red",
            )
        )