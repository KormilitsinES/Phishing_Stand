"""Управление состоянием развёртывания (JSON вместо текстового .deploy_state)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

DEFAULT_STATE_FILE: Final[Path] = Path(".deploy_state.json")


@dataclass
class StepRecord:
    """Запись о выполнении одного шага."""

    name: str
    status: str  # "done" | "failed" | "skipped"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message: str = ""


@dataclass
class DeployState:
    """Состояние развёртывания стенда."""

    path: Path = DEFAULT_STATE_FILE
    steps: dict[str, StepRecord] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    # ---------- Загрузка / сохранение ----------
    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        self.started_at = data.get("started_at", "")
        self.finished_at = data.get("finished_at", "")
        self.steps = {
            name: StepRecord(
                name=name,
                status=rec.get("status", "done"),
                timestamp=rec.get("timestamp", ""),
                message=rec.get("message", ""),
            )
            for name, rec in data.get("steps", {}).items()
        }

    def save(self) -> None:
        data = {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": {
                name: {
                    "status": rec.status,
                    "timestamp": rec.timestamp,
                    "message": rec.message,
                }
                for name, rec in self.steps.items()
            },
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- Работа с шагами ----------
    def is_step_done(self, name: str) -> bool:
        rec = self.steps.get(name)
        return rec is not None and rec.status == "done"

    def mark_step_done(self, name: str, message: str = "") -> None:
        self.steps[name] = StepRecord(name=name, status="done", message=message)
        self.save()

    def mark_step_failed(self, name: str, message: str = "") -> None:
        self.steps[name] = StepRecord(name=name, status="failed", message=message)
        self.save()

    def mark_step_skipped(self, name: str, message: str = "") -> None:
        self.steps[name] = StepRecord(name=name, status="skipped", message=message)
        self.save()

    def mark_started(self) -> None:
        self.started_at = datetime.now().isoformat()
        self.save()

    def mark_finished(self) -> None:
        self.finished_at = datetime.now().isoformat()
        self.save()

    def reset(self) -> None:
        self.steps.clear()
        self.started_at = ""
        self.finished_at = ""
        if self.path.exists():
            self.path.unlink()

    # ---------- Статистика ----------
    @property
    def completed_count(self) -> int:
        return sum(1 for r in self.steps.values() if r.status == "done")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.steps.values() if r.status == "failed")