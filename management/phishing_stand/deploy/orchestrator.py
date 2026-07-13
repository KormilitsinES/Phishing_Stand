"""Оркестратор: управляет порядком выполнения шагов."""
from __future__ import annotations

from datetime import datetime

from phishing_stand.config import Settings
from phishing_stand.deploy.steps.base import Step
from phishing_stand.logger import get_logger
from phishing_stand.state import DeployState
from phishing_stand.utils import require_root

log = get_logger("orchestrator")


class DeployOrchestrator:
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

    def run(self, *, resume: bool = False, dry_run: bool = False) -> bool:
        print("\n" + "=" * 60)
        print(" НАЧАЛО РАЗВЁРТЫВАНИЯ PHISHING STAND")
        print(f" Время: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f" Шагов: {len(self._steps)}")
        print(f" Домен: {self._settings.BASE_DOMAIN or 'не указан'}")
        print("=" * 60 + "\n")

        self._validate_dependencies()
        if not dry_run:
            self._check_root()

        self._state.mark_started()
        total = len(self._steps)

        for i, step in enumerate(self._steps, 1):
            prefix = f"[{i}/{total}]"

            if resume and step.is_completed():
                print(f"{prefix} {step.description} ... [ПРОПУЩЕНО]")
                continue

            if not step.pre_check():
                print(f"{prefix} {step.description} ... [ПРОПУЩЕНО (не выполнены условия)]")
                step.mark_skipped(message="pre_check failed")
                continue

            if dry_run:
                print(f"{prefix} {step.description} ... [DRY-RUN]")
                continue

            print(f"{prefix} {step.description} ... ", end="", flush=True)
            success = self._execute_step(step)

            if not success:
                print("[ОШИБКА]")
                self._print_failure_report()
                return False

            print("[OK]")

        self._state.mark_finished()
        print("\n" + "=" * 60)
        print(" РАЗВЁРТЫВАНИЕ УСПЕШНО ЗАВЕРШЕНО")
        print("=" * 60 + "\n")
        return True

    def _execute_step(self, step: Step) -> bool:
        try:
            success = step.execute()
            if success:
                step.mark_completed(message="ok")
                return True
            else:
                step.mark_failed(message="returned False")
                return False
        except Exception as e:
            step.mark_failed(message=str(e))
            log.exception(f"Исключение в шаге {step.name}: {e}")
            try:
                step.rollback()
            except Exception as rb:
                log.error(f"Ошибка при откате: {rb}")
            return False

    def _check_root(self) -> None:
        needs_root = any(s.requires_root for s in self._steps if not s.is_completed())
        if needs_root:
            require_root()

    def _validate_dependencies(self) -> None:
        names = {s.name for s in self._steps}
        for step in self._steps:
            for dep in step.depends_on:
                if dep not in names:
                    raise ValueError(f"Шаг '{step.name}' зависит от несуществующего шага '{dep}'")

    def _print_failure_report(self) -> None:
        print("\n" + "!" * 60)
        print(" РАЗВЁРТЫВАНИЕ ПРЕРВАНО ИЗ-ЗА ОШИБКИ")
        print(" Вы можете:")
        print("   1. Исправить проблему и запустить: phishing-stand deploy --resume")
        print("   2. Посмотреть состояние: phishing-stand status")
        print("!" * 60 + "\n")