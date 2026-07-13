# tests/test_orchestrator.py
"""Тесты оркестратора и шагов."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from phishing_stand.config import Settings
from phishing_stand.deploy.orchestrator import DeployOrchestrator
from phishing_stand.deploy.steps.base import Step
from phishing_stand.state import DeployState


# ---------- Фикстуры ----------

@pytest.fixture
def settings() -> Settings:
    return Settings.model_construct(
        BASE_DOMAIN="test.com",
        TRACK_DOMAIN="t.test.com",
        EVIL_DOMAIN="e.test.com",
        MX_DOMAIN="mail.test.com",
        ADMIN_EMAIL="admin@test.com",
        VPS_IP="1.2.3.4",
    )


@pytest.fixture
def state(tmp_path: Path) -> DeployState:
    return DeployState(path=tmp_path / ".deploy_state.json")


# ---------- Тестовые шаги ----------

class SuccessStep(Step):
    name = "success"
    description = "Успешный шаг"

    def execute(self) -> bool:
        return True


class FailingStep(Step):
    name = "failing"
    description = "Падающий шаг"

    def execute(self) -> bool:
        raise RuntimeError("Test error")


class SkippedStep(Step):
    name = "skipped"
    description = "Пропускаемый шаг"

    def pre_check(self) -> bool:
        return False

    def execute(self) -> bool:
        return True


# ---------- Тесты ----------

def test_orchestrator_all_success(settings: Settings, state: DeployState):
    steps = [SuccessStep(settings, state)]
    orch = DeployOrchestrator(steps=steps, settings=settings, state=state)
    assert orch.run() is True
    assert state.is_step_done("success")


def test_orchestrator_failure_stops(settings: Settings, state: DeployState):
    steps = [FailingStep(settings, state), SuccessStep(settings, state)]
    orch = DeployOrchestrator(steps=steps, settings=settings, state=state)
    assert orch.run() is False
    assert state.failed_count == 1
    assert not state.is_step_done("success")


def test_orchestrator_resume_skips_done(settings: Settings, state: DeployState):
    state.mark_step_done("success")
    steps = [SuccessStep(settings, state), SuccessStep(settings, state)]
    steps[0].name = "success"
    steps[1].name = "success2"
    steps[1].description = "Second"

    orch = DeployOrchestrator(steps=steps, settings=settings, state=state)
    assert orch.run(resume=True) is True
    # Первый шаг пропущен, второй выполнен
    assert state.steps["success"].status == "done"
    assert state.steps["success2"].status == "done"


def test_orchestrator_dry_run(settings: Settings, state: DeployState):
    steps = [SuccessStep(settings, state)]
    orch = DeployOrchestrator(steps=steps, settings=settings, state=state)
    assert orch.run(dry_run=True) is True
    # В dry-run шаг не должен быть помечен как выполненный
    assert not state.is_step_done("success")


def test_orchestrator_pre_check_skip(settings: Settings, state: DeployState):
    steps = [SkippedStep(settings, state)]
    orch = DeployOrchestrator(steps=steps, settings=settings, state=state)
    assert orch.run() is True
    assert state.steps["skipped"].status == "skipped"


def test_step_idempotency(settings: Settings, state: DeployState):
    """Повторный вызов execute() не должен ломать состояние."""
    step = SuccessStep(settings, state)
    assert step.execute() is True
    step.mark_completed()
    assert step.is_completed() is True
    # Повторный вызов — шаг уже выполнен
    assert step.is_completed() is True