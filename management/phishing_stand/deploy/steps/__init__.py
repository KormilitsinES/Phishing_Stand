# phishing_stand/deploy/steps/__init__.py
"""Реестр всех шагов развёртывания в правильном порядке."""
from __future__ import annotations

from typing import TYPE_CHECKING

from phishing_stand.deploy.steps.generate_env import GenerateEnvStep
from phishing_stand.deploy.steps.install_docker import InstallDockerStep
from phishing_stand.deploy.steps.system_update import SystemUpdateStep

if TYPE_CHECKING:
    from phishing_stand.deploy.steps.base import Step

# Порядок шагов важен! Каждый шаг может зависеть от предыдущих.
STEPS_REGISTRY: list[type["Step"]] = [
    SystemUpdateStep,
    InstallDockerStep,
    GenerateEnvStep,
    # На следующих шагах добавим:
    # CertbotStep,
    # DockerComposeStep,
    # DKIMStep,
    # FinalizeStep,
]

__all__ = ["STEPS_REGISTRY"]