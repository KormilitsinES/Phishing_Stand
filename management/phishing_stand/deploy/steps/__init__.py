# phishing_stand/deploy/steps/__init__.py
"""Реестр всех шагов развёртывания в правильном порядке."""
from __future__ import annotations

from typing import TYPE_CHECKING

from phishing_stand.deploy.steps.certbot import CertbotStep
from phishing_stand.deploy.steps.dkim import DKIMStep
from phishing_stand.deploy.steps.docker_compose import DockerComposeStep
from phishing_stand.deploy.steps.finalize import FinalizeStep
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
    CertbotStep,
    DockerComposeStep,
    DKIMStep,
    FinalizeStep,
]

__all__ = ["STEPS_REGISTRY"]