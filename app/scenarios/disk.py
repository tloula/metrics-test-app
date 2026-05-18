"""Disk I/O scenario: write -> fsync -> delete temp files in a loop."""

from __future__ import annotations

import os
import tempfile
import threading
import time

from app import state

MAX_DURATION_S = 600
MAX_FILE_MB = 256
MAX_ITERATIONS = 1000

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def stop() -> dict:
    global _thread
    _stop_event.set()
    if _thread:
        _thread.join(timeout=2)
        _thread = None
    state.unregister("disk.io")
    return {"stopped": True}


def run(mb: int, iterations: int) -> dict:
    mb = max(1, min(int(mb), MAX_FILE_MB))
    iterations = max(1, min(int(iterations), MAX_ITERATIONS))
    stop()
    _stop_event.clear()
    run = state.ScenarioRun(
        name="disk.io",
        started_at=time.time(),
        ends_at=None,
        params={"mb": mb, "iterations": iterations},
        detail={"bytes_written": 0, "files": 0},
    )
    state.register(run)

    def runner() -> None:
        chunk = b"\x42" * (1024 * 1024)
        try:
            for i in range(iterations):
                if _stop_event.is_set():
                    break
                fd, path = tempfile.mkstemp(prefix="embr-metrics-", suffix=".bin")
                try:
                    with os.fdopen(fd, "wb") as f:
                        for _ in range(mb):
                            f.write(chunk)
                            run.detail["bytes_written"] += len(chunk)
                        f.flush()
                        os.fsync(f.fileno())
                    run.detail["files"] = i + 1
                finally:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        finally:
            state.unregister("disk.io")

    global _thread
    _thread = threading.Thread(target=runner, daemon=True)
    _thread.start()
    return {"started": True, "mb": mb, "iterations": iterations}
