"""Network load scenarios: egress (download), ingress (handled by /api route),
and sustained oscillation (periodic egress bursts).
"""

from __future__ import annotations

import asyncio
import threading
import time

import httpx

from app import state

MAX_DURATION_S = 600
MAX_PAYLOAD_MB = 500
# Cloudflare's speed test endpoint — generates an N-byte response on demand and
# is reachable from essentially every cloud egress. Default 100 MB per request.
DEFAULT_EGRESS_URL = "https://speed.cloudflare.com/__down?bytes=104857600"

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def stop() -> dict:
    global _thread
    _stop_event.set()
    if _thread:
        _thread.join(timeout=2)
        _thread = None
    state.unregister("network.egress")
    state.unregister("network.oscillate")
    return {"stopped": True}


async def _download_once(url: str) -> int:
    bytes_read = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                bytes_read += len(chunk)
                if _stop_event.is_set():
                    break
    return bytes_read


def egress(url: str, repeat: int) -> dict:
    repeat = max(1, min(int(repeat), 20))
    url = url or DEFAULT_EGRESS_URL
    stop()
    _stop_event.clear()
    started = time.time()
    run = state.ScenarioRun(
        name="network.egress",
        started_at=started,
        ends_at=None,
        params={"url": url, "repeat": repeat},
        detail={"bytes_total": 0, "iterations": 0},
    )
    state.register(run)

    def runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            for i in range(repeat):
                if _stop_event.is_set():
                    break
                try:
                    n = loop.run_until_complete(_download_once(url))
                    run.detail["bytes_total"] += n
                    run.detail["iterations"] = i + 1
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    run.detail["error"] = msg
                    state.record_error("network.egress", msg, {"url": url})
                    break
        finally:
            loop.close()
            state.unregister("network.egress")

    global _thread
    _thread = threading.Thread(target=runner, daemon=True)
    _thread.start()
    return {"started": True, "url": url, "repeat": repeat}


def oscillate(period_s: float, duration_s: float, url: str) -> dict:
    period_s = max(2.0, min(float(period_s), 120.0))
    duration_s = max(1.0, min(float(duration_s), MAX_DURATION_S))
    url = url or DEFAULT_EGRESS_URL
    stop()
    _stop_event.clear()
    until = time.time() + duration_s
    run = state.ScenarioRun(
        name="network.oscillate",
        started_at=time.time(),
        ends_at=until,
        params={"period_s": period_s, "duration_s": duration_s, "url": url},
        detail={"bytes_total": 0, "iterations": 0},
    )
    state.register(run)

    def runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            while not _stop_event.is_set() and time.time() < until:
                burst_start = time.time()
                try:
                    n = loop.run_until_complete(_download_once(url))
                    run.detail["bytes_total"] += n
                    run.detail["iterations"] += 1
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    run.detail["error"] = msg
                    state.record_error("network.oscillate", msg, {"url": url})
                # idle for the remainder of the period (gap = oscillation)
                elapsed = time.time() - burst_start
                gap = max(0.0, period_s - elapsed)
                end_gap = time.time() + gap
                while time.time() < end_gap and not _stop_event.is_set():
                    time.sleep(0.25)
        finally:
            loop.close()
            state.unregister("network.oscillate")

    global _thread
    _thread = threading.Thread(target=runner, daemon=True)
    _thread.start()
    return {"started": True, "period_s": period_s, "duration_s": duration_s, "url": url}
