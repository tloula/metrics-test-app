"""FastAPI entrypoint for the Embr metrics test app.

Exposes:
- GET  /              -> built React UI (mounted from STATIC_DIR)
- GET  /health        -> 200 unless a health-fail scenario is active
- GET  /api/status    -> active scenarios + process metrics snapshot
- POST /api/cpu/*     -> CPU scenarios
- POST /api/memory/*  -> memory scenarios
- POST /api/network/* -> network scenarios
- POST /api/disk/io   -> disk I/O scenario
- POST /api/health/*  -> health-failure + crash scenarios
- POST /api/stop/all  -> stop every running scenario
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import state
from app.scenarios import cpu, disk
from app.scenarios import health as health_scenarios
from app.scenarios import memory, network

# In production (Embr deploy) the UI is staged at /output/static.
# Locally it lives next to this file at ../ui/dist.
def _resolve_static_dir() -> Path | None:
    candidates = [
        Path(os.environ.get("STATIC_DIR", "")),
        Path("/output/static"),
        Path(__file__).resolve().parent.parent / "ui" / "dist",
    ]
    for p in candidates:
        if p and p.exists() and (p / "index.html").exists():
            return p
    return None


STATIC_DIR = _resolve_static_dir()

app = FastAPI(title="Embr Metrics Test App", version="0.1.0")

_process = psutil.Process()
# Prime cpu_percent so subsequent calls return meaningful values.
_process.cpu_percent(interval=None)


# -------- health + status --------


@app.get("/health")
def health() -> Any:
    if time.time() < state.health_fail_until:
        return PlainTextResponse("unhealthy", status_code=500)
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict:
    try:
        vm = psutil.virtual_memory()
        mem_info = _process.memory_info()
        net = psutil.net_io_counters()
        proc_cpu = _process.cpu_percent(interval=None)
        sys_cpu = psutil.cpu_percent(interval=None)
    except Exception as e:
        return {"error": str(e), "scenarios": state.snapshot()}

    return {
        "now": time.time(),
        "scenarios": state.snapshot(),
        "process": {
            "pid": _process.pid,
            "cpu_percent": proc_cpu,
            "rss_bytes": mem_info.rss,
            "num_threads": _process.num_threads(),
        },
        "system": {
            "cpu_percent": sys_cpu,
            "memory_total_bytes": vm.total,
            "memory_used_bytes": vm.total - vm.available,
            "memory_available_bytes": vm.available,
        },
        "network": {
            "rx_bytes": net.bytes_recv,
            "tx_bytes": net.bytes_sent,
        },
        "health_fail_remaining_s": max(0.0, state.health_fail_until - time.time()),
    }


# -------- request models --------


class CpuSpike(BaseModel):
    duration_s: float = 30
    workers: int = 2


class CpuOscillate(BaseModel):
    period_s: float = 20
    duration_s: float = 120
    workers: int = 2


class MemoryGrow(BaseModel):
    mb: int = 256
    hold_s: float = 60


class MemoryOscillate(BaseModel):
    min_mb: int = 64
    max_mb: int = 512
    period_s: float = 30
    duration_s: float = 180


class NetworkEgress(BaseModel):
    url: str = ""
    repeat: int = 1


class NetworkOscillate(BaseModel):
    period_s: float = 20
    duration_s: float = 180
    url: str = ""


class DiskIO(BaseModel):
    mb: int = 64
    iterations: int = 10


class HealthFail(BaseModel):
    duration_s: float = 30


# -------- CPU --------


@app.post("/api/cpu/spike")
def cpu_spike(body: CpuSpike) -> dict:
    return cpu.spike(body.duration_s, body.workers)


@app.post("/api/cpu/oscillate")
def cpu_oscillate(body: CpuOscillate) -> dict:
    return cpu.oscillate(body.period_s, body.duration_s, body.workers)


@app.post("/api/cpu/stop")
def cpu_stop() -> dict:
    return cpu.stop()


# -------- memory --------


@app.post("/api/memory/grow")
def memory_grow(body: MemoryGrow) -> dict:
    return memory.grow(body.mb, body.hold_s)


@app.post("/api/memory/oscillate")
def memory_oscillate(body: MemoryOscillate) -> dict:
    return memory.oscillate(body.min_mb, body.max_mb, body.period_s, body.duration_s)


@app.post("/api/memory/stop")
def memory_stop() -> dict:
    return memory.stop()


# -------- network --------


@app.post("/api/network/egress")
def network_egress(body: NetworkEgress) -> dict:
    return network.egress(body.url, body.repeat)


@app.post("/api/network/oscillate")
def network_oscillate(body: NetworkOscillate) -> dict:
    return network.oscillate(body.period_s, body.duration_s, body.url)


@app.post("/api/network/stop")
def network_stop() -> dict:
    return network.stop()


@app.post("/api/network/ingress")
async def network_ingress(request: Request) -> dict:
    """Accept and discard a large payload — drives ingress bytes on the instance.

    Streams the body so we never buffer the entire thing in RAM.
    """
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > network.MAX_PAYLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"Payload exceeds {network.MAX_PAYLOAD_MB} MB cap")
    return {"received_bytes": total}


# -------- disk --------


@app.post("/api/disk/io")
def disk_io(body: DiskIO) -> dict:
    return disk.run(body.mb, body.iterations)


@app.post("/api/disk/stop")
def disk_stop() -> dict:
    return disk.stop()


# -------- health failure + crash --------


@app.post("/api/health/fail")
def health_fail(body: HealthFail) -> dict:
    return health_scenarios.fail_for(body.duration_s)


@app.post("/api/crash")
def crash(confirm: str = Query("", description="must be 'yes'")) -> dict:
    if confirm != "yes":
        raise HTTPException(400, "confirm=yes query param is required")
    return health_scenarios.crash(delay_s=1.0)


# -------- global stop --------


@app.post("/api/stop/all")
def stop_all() -> dict:
    return {
        "cpu": cpu.stop(),
        "memory": memory.stop(),
        "network": network.stop(),
        "disk": disk.stop(),
    }


# -------- UI (mounted last so /api routes win) --------

if STATIC_DIR is not None:
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/{path:path}")
    def spa_fallback(path: str) -> FileResponse:
        # Let any non-API GET render the SPA shell.
        candidate = STATIC_DIR / path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(STATIC_DIR / "index.html"))
else:

    @app.get("/")
    def no_ui() -> JSONResponse:
        return JSONResponse(
            {
                "message": "UI not built yet. Run `cd ui && npm install && npm run build`, or use the API directly.",
                "docs": "/docs",
            }
        )
