# tests/test_steps.py
"""Тесты шагов развёртывания."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from phishing_stand.config import Settings
from phishing_stand.deploy.steps.docker_compose import DockerComposeStep
from phishing_stand.deploy.steps.finalize import FinalizeStep
from phishing_stand.state import DeployState


@pytest.fixture
def settings() -> Settings:
    return Settings(
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


def test_docker_compose_generate(settings: Settings, state: DeployState, tmp_path: Path, monkeypatch):
    """Тестируем генерацию docker-compose.yml и запуск."""
    monkeypatch.chdir(tmp_path)
    step = DockerComposeStep(settings, state)

    # Мокаем там, где функции используются (в модуле docker_compose)
    with patch("phishing_stand.deploy.steps.docker_compose.compose_command") as mock_compose, \
            patch("phishing_stand.deploy.steps.docker_compose.run") as mock_run:
        mock_compose.return_value = ["docker", "compose"]
        # Имитируем успешный ответ docker compose ps для _wait_for_containers
        mock_run.return_value = MagicMock(
            ok=True,
            stdout='{"Name": "gophish", "State": "running"}\n',
            returncode=0
        )

        assert step.execute() is True

    compose_file = tmp_path / "docker-compose.yml"
    assert compose_file.exists()
    content = compose_file.read_text()
    assert "test.com" in content
    assert "gophish" in content


def test_finalize_prints_summary(settings: Settings, state: DeployState, capsys):
    """Тестируем вывод итоговой информации."""
    step = FinalizeStep(settings, state)

    # Мокаем там, где функции используются (в модуле finalize)
    with patch("phishing_stand.deploy.steps.finalize.compose_command") as mock_compose, \
            patch("phishing_stand.deploy.steps.finalize.run") as mock_run:
        mock_compose.return_value = ["docker", "compose"]
        mock_run.return_value = MagicMock(
            ok=True,
            stdout="CONTAINER ID   NAME      STATUS\n123   gophish   running\n",
            returncode=0
        )

        assert step.execute() is True