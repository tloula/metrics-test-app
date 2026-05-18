# Embr Metrics Test App

A small Python + React app for **exercising every metric** that the Embr Portal and CLI surface (per-instance CPU %, memory used/total, network rx/tx + lifetime totals, process metrics, plus health-check restore behavior).

The UI is a grid of scenario cards — pick one, set parameters, hit **Start**, then watch the values move in Embr Portal / `embr` CLI.

> ⚠️ This is a **load-testing tool**. Don't deploy it into a shared environment without coordination — it intentionally burns CPU, allocates memory, downloads files, and can crash itself.

## Scenarios

| Scenario | What it does |
|---|---|
| **CPU spike** | Pins N threads at 100% for a fixed duration. |
| **CPU oscillation** | Sine-wave duty cycle — CPU rises and falls every period. |
| **Memory grow + hold** | Allocates N MB and holds it for `hold_s`. |
| **Memory oscillation** | Grows/shrinks between min and max MB cyclically. |
| **Network egress** | Streams a large file from a public URL N times. |
| **Network oscillation** | Periodic egress bursts every period for the duration. |
| **Network ingress** | Browser uploads N MB to `/api/network/ingress`. |
| **Disk I/O** | Writes & fsyncs temp files (N MB × iterations), then deletes. |
| **Health-check failure** | Makes `/health` return 500 for N seconds — triggers Embr auto-restore after ~3 consecutive failures. |
| **Crash** | `os._exit(1)` — Embr should restore the sandbox from snapshot. |

All scenarios are bounded server-side:
- CPU workers capped at `cpu_count * 4`
- Memory capped at 80% of system memory (hard ceiling 4 GB)
- Network payloads capped at 500 MB
- All durations capped at 600 s

## Local development

Requires Python 3.12+ and Node 20+.

**Backend:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # or `source .venv/bin/activate` on Unix
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

**Frontend (separate terminal):**

```powershell
cd ui
npm install
npm run dev
```

Then open <http://localhost:5173> — Vite proxies `/api` and `/health` to the backend on 8080.

To test the production build path locally:

```powershell
cd ui ; npm run build ; cd ..
uvicorn app.main:app --port 8080
# UI now served from http://localhost:8080/
```

## Deploying to Embr

1. **Create a GitHub repo** with this codebase (e.g. `<you>/metrics-test-app`).
2. **Install the Embr GitHub App** on the repo and grab the installation ID:
   ```bash
   embr installations config
   ```
3. **One-command deploy:**
   ```bash
   embr quickstart deploy <owner>/metrics-test-app -i <installation_id>
   ```

That command creates the project + a `production` environment, fetches the default branch, builds, and deploys.

### How the build works

`embr.yaml` uses a custom `buildCommand` that:

1. Installs UI deps with `npm ci` and builds the Vite bundle.
2. Stages `app/`, `requirements.txt`, and the built UI into `/output/`.
3. Creates a Python 3.12 venv at `/output/pythonenv3.12/` and installs Python deps into it.

The `run.startCommand` uses the venv's `uvicorn` (per the Embr docs note — Oryx does not auto-activate the venv when a custom `startCommand` is provided).

The app serves the built UI from `/output/static` and exposes the API under `/api/*` and `/health`.

## Where to watch the metrics

After deploying, open the project in the Embr Portal:

- **Overview → Instances table**: CPU %, Memory used/total, Network rx/tx rate + lifetime.
- **Overview → Activity → Processes**: per-process CPU % and memory.
- **CLI:** `embr environments get -p <projectId> -e <envId>` and `embr logs` for live container logs.

Run a scenario, then watch the values move within seconds.

## API reference (quick)

| Method | Path | Body / params |
|---|---|---|
| GET | `/health` | — |
| GET | `/api/status` | — |
| POST | `/api/cpu/spike` | `{ duration_s, workers }` |
| POST | `/api/cpu/oscillate` | `{ period_s, duration_s, workers }` |
| POST | `/api/cpu/stop` | — |
| POST | `/api/memory/grow` | `{ mb, hold_s }` |
| POST | `/api/memory/oscillate` | `{ min_mb, max_mb, period_s, duration_s }` |
| POST | `/api/memory/stop` | — |
| POST | `/api/network/egress` | `{ url, repeat }` |
| POST | `/api/network/oscillate` | `{ period_s, duration_s, url }` |
| POST | `/api/network/ingress` | raw bytes (octet-stream) |
| POST | `/api/network/stop` | — |
| POST | `/api/disk/io` | `{ mb, iterations }` |
| POST | `/api/disk/stop` | — |
| POST | `/api/health/fail` | `{ duration_s }` |
| POST | `/api/crash?confirm=yes` | — |
| POST | `/api/stop/all` | — |

Full OpenAPI spec: `/docs` (FastAPI auto-generated).
