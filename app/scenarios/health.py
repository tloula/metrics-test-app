"""Health-failure and crash scenarios."""

from __future__ import annotations

import os
import threading
import time

from app import state

MAX_FAIL_S = 300


def fail_for(duration_s: float) -> dict:
    duration_s = max(1.0, min(float(duration_s), MAX_FAIL_S))
    until = time.time() + duration_s
    state.health_fail_until = until
    state.register(
        state.ScenarioRun(
            name="health.fail",
            started_at=time.time(),
            ends_at=until,
            params={"duration_s": duration_s},
        )
    )

    def cleanup() -> None:
        while time.time() < until:
            time.sleep(0.5)
        state.unregister("health.fail")

    threading.Thread(target=cleanup, daemon=True).start()
    return {"failing_until": until, "duration_s": duration_s}


def crash(delay_s: float = 1.0) -> dict:
    """Schedule a hard process exit so the response can flush first."""

    def killer() -> None:
        time.sleep(max(0.1, min(float(delay_s), 5.0)))
        os._exit(1)

    threading.Thread(target=killer, daemon=True).start()
    return {"crashing_in_s": delay_s}
