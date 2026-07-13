# tests/test_config.py
"""Тесты конфигурации."""
from __future__ import annotations

from pathlib import Path

import pytest

from phishing_stand.config import Settings


def test_settings_valid():
    s = Settings(
        BASE_DOMAIN="example.com",
        TRACK_DOMAIN="t.example.com",
        EVIL_DOMAIN="e.example.com",
        MX_DOMAIN="mail.example.com",
        ADMIN_EMAIL="admin@example.com",
        VPS_IP="1.2.3.4",
    )
    assert s.BASE_DOMAIN == "example.com"


def test_settings_invalid_domain():
    with pytest.raises(ValueError):
        Settings(
            BASE_DOMAIN="-invalid.com",
            TRACK_DOMAIN="t.example.com",
            EVIL_DOMAIN="e.example.com",
            MX_DOMAIN="mail.example.com",
            ADMIN_EMAIL="admin@example.com",
            VPS_IP="1.2.3.4",
        )


def test_settings_invalid_ip():
    with pytest.raises(ValueError):
        Settings(
            BASE_DOMAIN="example.com",
            TRACK_DOMAIN="t.example.com",
            EVIL_DOMAIN="e.example.com",
            MX_DOMAIN="mail.example.com",
            ADMIN_EMAIL="admin@example.com",
            VPS_IP="999.999.999.999",
        )


def test_settings_from_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BASE_DOMAIN=test.com\n"
        "TRACK_DOMAIN=t.test.com\n"
        "EVIL_DOMAIN=e.test.com\n"
        "MX_DOMAIN=mail.test.com\n"
        "ADMIN_EMAIL=admin@test.com\n"
        "VPS_IP=10.0.0.1\n"
    )
    s = Settings.from_env_file(env_file)
    assert s.BASE_DOMAIN == "test.com"
    assert s.VPS_IP == "10.0.0.1"


def test_settings_from_env_file_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Settings.from_env_file(tmp_path / "nonexistent.env")