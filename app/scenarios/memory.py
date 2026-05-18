"""Memory load scenarios: hold N MB or oscillate between two sizes."""

from __future__ import annotations

import math
import threading
import time

import psutil

from app import state

MAX_DURATION_S = 600
ABSOLUTE_MAX_MB = 4096  # hard ceiling regardless of host


def _max_allowed_mb() -> int:
    # Respect cgroup limit if present; else 80% of system memory.
    try:
        vm = psutil.virtual_memory()
        return max(64, min(ABSOLUTE_MAX_MB, int(vm.total * 0.8 / (1024 * 1024))))
    except Exception:
        return ABSOLUTE_MAX_MB


_lock = threading.Lock()
_buffers: list[bytearray] = []
_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _allocate(target_mb: int) -> None:
    with _lock:
        _buffers.clear()
        # 1 MB chunks so allocation is incremental and touches pages
        chunk = 1024 * 1024
        for _ in range(target_mb):
            buf = bytearray(chunk)
            # Touch the buffer so the OS actually backs it with real pages
            for i in range(0, chunk, 4096):
                buf[i] = 1
            _buffers.append(buf)


def _release() -> None:
    with _lock:
        _buffers.clear()


def stop() -> dict:
    global _thread
    _stop_event.set()
    if _thread:
        _thread.join(timeout=2)
        _thread = None
    _release()
    state.unregister("memory.grow")
    state.unregister("memory.oscillate")
    return {"stopped": True}


def grow(mb: int, hold_s: float) -> dict:
    cap = _max_allowed_mb()
    mb = max(1, min(int(mb), cap))
    hold_s = max(1.0, min(float(hold_s), MAX_DURATION_S))
    stop()
    _stop_event.clear()
    until = time.time() + hold_s

    def runner() -> None:
        _allocate(mb)
        while not _stop_event.is_set() and time.time() < until:
            time.sleep(0.5)
        _release()
        state.unregister("memory.grow")

    global _thread
    _thread = threading.Thread(target=runner, daemon=True)
    _thread.start()
    state.register(
        state.ScenarioRun(
            name="memory.grow",
            started_at=time.time(),
            ends_at=until,
            params={"mb": mb, "hold_s": hold_s},
        )
    )
    return {"started": True, "mb": mb, "hold_s": hold_s, "cap_mb": cap}


def oscillate(min_mb: int, max_mb: int, period_s: float, duration_s: float) -> dict:
    cap = _max_allowed_mb()
    min_mb = max(1, min(int(min_mb), cap))
    max_mb = max(min_mb, min(int(max_mb), cap))
    period_s = max(2.0, min(float(period_s), 120.0))
    duration_s = max(1.0, min(float(duration_s), MAX_DURATION_S))
    stop()
    _stop_event.clear()
    until = time.time() + duration_s

    def runner() -> None:
        while not _stop_event.is_set() and time.time() < until:
            phase = (time.time() % period_s) / period_s
            duty = 0.5 + 0.5 * math.sin(2 * math.pi * phase)
            target = int(min_mb + (max_mb - min_mb) * duty)
            _allocate(target)
            time.sleep(0.25)
        _release()
        state.unregister("memory.oscillate")

    global _thread
    _thread = threading.Thread(target=runner, daemon=True)
    _thread.start()
    state.register(
        state.ScenarioRun(
            name="memory.oscillate",
            started_at=time.time(),
            ends_at=until,
            params={
                "min_mb": min_mb,
                "max_mb": max_mb,
                "period_s": period_s,
                "duration_s": duration_s,
            },
        )
    )
    return {
        "started": True,
        "min_mb": min_mb,
        "max_mb": max_mb,
        "period_s": period_s,
        "duration_s": duration_s,
        "cap_mb": cap,
    }
