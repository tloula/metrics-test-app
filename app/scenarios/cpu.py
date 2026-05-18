"""CPU load scenarios: sustained spike + sine-wave oscillation."""

from __future__ import annotations

import math
import os
import threading
import time

from app import state

MAX_DURATION_S = 600
MAX_WORKERS = max(1, (os.cpu_count() or 1) * 4)

_stop_event = threading.Event()
_threads: list[threading.Thread] = []


def _busy_loop(stop: threading.Event, until: float) -> None:
    x = 0.0
    while not stop.is_set() and time.time() < until:
        # tight math loop — keeps a core pegged
        for _ in range(100_000):
            x = (x + 1.234) * 1.0001
            if x > 1e12:
                x = 0.0


def _oscillate_loop(stop: threading.Event, until: float, period_s: float) -> None:
    """Sine-wave duty cycle in 100 ms slices."""
    slice_s = 0.1
    while not stop.is_set() and time.time() < until:
        # duty in [0.05, 0.95] following a sine wave
        phase = (time.time() % period_s) / period_s
        duty = 0.5 + 0.45 * math.sin(2 * math.pi * phase)
        busy = slice_s * duty
        idle = slice_s - busy
        end_busy = time.time() + busy
        x = 0.0
        while time.time() < end_busy and not stop.is_set():
            x = (x + 1.234) * 1.0001
            if x > 1e12:
                x = 0.0
        if idle > 0:
            time.sleep(idle)

trevorloula@outlook.com pas

def stop() -> dict:
    _stop_event.set()
    for t in _threads:
        t.join(timeout=2)
    _threads.clear()
    state.unregister("cpu.spike")
    state.unregister("cpu.oscillate")
    return {"stopped": True}


def spike(duration_s: float, workers: int) -> dict:
    duration_s = max(1.0, min(float(duration_s), MAX_DURATION_S))
    workers = max(1, min(int(workers), MAX_WORKERS))
    stop()
    _stop_event.clear()
    until = time.time() + duration_s
    for _ in range(workers):
        t = threading.Thread(target=_busy_loop, args=(_stop_event, until), daemon=True)
        t.start()
        _threads.append(t)
    state.register(
        state.ScenarioRun(
            name="cpu.spike",
            started_at=time.time(),
            ends_at=until,
            params={"duration_s": duration_s, "workers": workers},
        )
    )
    return {"started": True, "duration_s": duration_s, "workers": workers}


def oscillate(period_s: float, duration_s: float, workers: int) -> dict:
    duration_s = max(1.0, min(float(duration_s), MAX_DURATION_S))
    period_s = max(1.0, min(float(period_s), 120.0))
    workers = max(1, min(int(workers), MAX_WORKERS))
    stop()
    _stop_event.clear()
    until = time.time() + duration_s
    for _ in range(workers):
        t = threading.Thread(
            target=_oscillate_loop, args=(_stop_event, until, period_s), daemon=True
        )
        t.start()
        _threads.append(t)
    state.register(
        state.ScenarioRun(
            name="cpu.oscillate",
            started_at=time.time(),
            ends_at=until,
            params={"period_s": period_s, "duration_s": duration_s, "workers": workers},
        )
    )
    return {"started": True, "duration_s": duration_s, "period_s": period_s, "workers": workers}
