"""Shared mutable state for active scenarios.

Each scenario registers itself here so /api/status can report what's running
and so duplicate scenarios can no-op or replace prior runs cleanly.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScenarioRun:
    name: str
    started_at: float
    ends_at: float | None
    params: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)


_lock = threading.Lock()
_active: dict[str, ScenarioRun] = {}

# Health-fail flag (set by /api/health/fail)
health_fail_until: float = 0.0

# Recent errors per scenario name, retained for ERROR_TTL_S
_errors: dict[str, dict[str, Any]] = {}
ERROR_TTL_S = 60.0


def record_error(scenario: str, message: str, extra: dict[str, Any] | None = None) -> None:
    with _lock:
        _errors[scenario] = {
            "scenario": scenario,
            "message": message,
            "at": time.time(),
            "extra": extra or {},
        }


def recent_errors() -> list[dict[str, Any]]:
    now = time.time()
    with _lock:
        keep = {k: v for k, v in _errors.items() if now - v["at"] <= ERROR_TTL_S}
        _errors.clear()
        _errors.update(keep)
        return sorted(keep.values(), key=lambda e: e["at"], reverse=True)


def register(run: ScenarioRun) -> None:
    with _lock:
        _active[run.name] = run


def unregister(name: str) -> None:
    with _lock:
        _active.pop(name, None)


def snapshot() -> list[dict[str, Any]]:
    now = time.time()
    with _lock:
        items = list(_active.values())
    out: list[dict[str, Any]] = []
    for r in items:
        out.append(
            {
                "name": r.name,
                "started_at": r.started_at,
                "ends_at": r.ends_at,
                "remaining_s": max(0.0, r.ends_at - now) if r.ends_at else None,
                "params": r.params,
                "detail": r.detail,
            }
        )
    return out
