"""Общие утилиты: subprocess, проверки окружения, работа с файлами."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

from phishing_stand.logger import get_logger

log = get_logger("utils")

DEFAULT_TIMEOUT: Final[int] = 600  # 10 минут


@dataclass
class RunResult:
    """Результат выполнения команды."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    cmd: str | Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
    capture: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    shell: bool | None = None,
) -> RunResult:
    """Безопасная обёртка над subprocess.run.

    - `shell` по умолчанию выставляется автоматически: True, если cmd — строка.
    - `capture=True` — перехватывает stdout/stderr.
    - `check=True` — бросает RuntimeError при ненулевом коде возврата.
    """
    if isinstance(cmd, str):
        args: str | Sequence[str] = cmd
        use_shell = shell if shell is not None else True
    else:
        args = list(cmd)
        use_shell = shell if shell is not None else False

    merged_env = None
    if env is not None:
        merged_env = {**os.environ, **env}

    log.debug(f"$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")

    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            env=merged_env,
            shell=use_shell,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Команда превысила таймаут {timeout}s: {cmd}") from e

    result = RunResult(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )

    if check and not result.ok:
        raise RuntimeError(
            f"Команда завершилась с кодом {result.returncode}: {cmd}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result


# ---------- Проверки окружения ----------

def require_root() -> None:
    """Завершает выполнение, если скрипт запущен не от root."""
    if os.geteuid() != 0:
        raise PermissionError("Требуется запуск от имени root (sudo)")


def require_command(name: str) -> Path:
    """Возвращает путь к исполняемому файлу или бросает ошибку."""
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(f"Необходимая утилита не найдена: {name}")
    return Path(path)


def is_docker_running() -> bool:
    """Проверяет, запущен ли Docker daemon."""
    try:
        r = run(["docker", "info"], capture=True, timeout=10)
        return r.ok
    except (RuntimeError, FileNotFoundError):
        return False


def compose_command() -> list[str]:
    """Возвращает команду docker compose (v2) или docker-compose (v1)."""
    # Сначала пробуем `docker compose`
    r = run(["docker", "compose", "version"], capture=True, timeout=10)
    if r.ok:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    raise RuntimeError("Не найден docker compose (v2) или docker-compose (v1)")


# ---------- Работа с файлами ----------

def ensure_dir(path: Path) -> Path:
    """Создаёт директорию, если её нет."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_copy(src: Path, dst: Path) -> None:
    """Копирует файл или директорию с сохранением метаданных."""
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=False)
    elif src.is_file():
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
    else:
        raise FileNotFoundError(f"Источник не найден: {src}")