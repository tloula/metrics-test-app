import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, Status } from './api';

function formatBytes(b: number | undefined): string {
  if (b === undefined) return '—';
  if (b < 1024) return `${b} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = b / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function useStatus() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.status();
        if (alive) {
          setStatus(s);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(String(e));
      }
    };
    tick();
    const id = setInterval(tick, 1500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);
  return { status, error };
}

type ScenarioCardProps = {
  title: string;
  description: string;
  activeNames: string[];
  scenarios: Status['scenarios'];
  children: React.ReactNode;
};

function ScenarioCard({ title, description, activeNames, scenarios, children }: ScenarioCardProps) {
  const active = scenarios.find((s) => activeNames.includes(s.name));
  return (
    <div className="card">
      <h2>
        {title}
        {active && <span className="badge running">running</span>}
      </h2>
      <div className="desc">{description}</div>
      {children}
      {active && (
        <div className="log">
          {active.name} · started {new Date(active.started_at * 1000).toLocaleTimeString()}
          {active.remaining_s !== null && active.remaining_s !== undefined
            ? ` · ${active.remaining_s.toFixed(0)}s left`
            : ''}
          {'\n'}
          {JSON.stringify({ ...active.params, ...active.detail }, null, 0)}
        </div>
      )}
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="field" style={{ gridColumn: 'span 2' }}>
      <label>{label}</label>
      <input type="text" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

export default function App() {
  const { status, error } = useStatus();
  const [log, setLog] = useState<string>('');

  const run = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    try {
      const r = await fn();
      setLog(`✓ ${label}: ${JSON.stringify(r)}`);
    } catch (e) {
      setLog(`✗ ${label}: ${String(e)}`);
    }
  }, []);

  // CPU
  const [cpuSpikeDur, setCpuSpikeDur] = useState(30);
  const [cpuSpikeW, setCpuSpikeW] = useState(2);
  const [cpuOscPeriod, setCpuOscPeriod] = useState(20);
  const [cpuOscDur, setCpuOscDur] = useState(120);
  const [cpuOscW, setCpuOscW] = useState(2);

  // Memory
  const [memGrowMb, setMemGrowMb] = useState(256);
  const [memGrowHold, setMemGrowHold] = useState(60);
  const [memMin, setMemMin] = useState(64);
  const [memMax, setMemMax] = useState(512);
  const [memPeriod, setMemPeriod] = useState(30);
  const [memDur, setMemDur] = useState(180);

  // Network
  const [netUrl, setNetUrl] = useState('');
  const [netRepeat, setNetRepeat] = useState(1);
  const [netOscPeriod, setNetOscPeriod] = useState(20);
  const [netOscDur, setNetOscDur] = useState(180);
  const [netIngressMb, setNetIngressMb] = useState(50);

  // Disk
  const [diskMb, setDiskMb] = useState(64);
  const [diskIter, setDiskIter] = useState(10);

  // Health
  const [healthDur, setHealthDur] = useState(30);

  const scenarios = status?.scenarios ?? [];
  const healthFailing = (status?.health_fail_remaining_s ?? 0) > 0;

  const memUsedPct = useMemo(() => {
    if (!status?.system) return null;
    return (
      (status.system.memory_used_bytes / Math.max(1, status.system.memory_total_bytes)) * 100
    );
  }, [status]);

  return (
    <div className="app">
      <div className="app-header">
        <h1>Embr Metrics Test App</h1>
        <div className="actions">
          <button className="secondary" onClick={() => run('stop all', api.stopAll)}>
            Stop all
          </button>
        </div>
      </div>

      {error && <div className="log">connection error: {error}</div>}

      <div className="metrics-bar">
        <div className="metric">
          <span className="label">System CPU</span>
          <span className="value">
            {status?.system ? `${status.system.cpu_percent.toFixed(1)}%` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="label">Process CPU</span>
          <span className="value">
            {status?.process ? `${status.process.cpu_percent.toFixed(1)}%` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="label">Memory used</span>
          <span className="value">
            {status?.system
              ? `${formatBytes(status.system.memory_used_bytes)} / ${formatBytes(status.system.memory_total_bytes)}${memUsedPct !== null ? ` (${memUsedPct.toFixed(0)}%)` : ''}`
              : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="label">Process RSS</span>
          <span className="value">{formatBytes(status?.process?.rss_bytes)}</span>
        </div>
        <div className="metric">
          <span className="label">Net rx</span>
          <span className="value">{formatBytes(status?.network?.rx_bytes)}</span>
        </div>
        <div className="metric">
          <span className="label">Net tx</span>
          <span className="value">{formatBytes(status?.network?.tx_bytes)}</span>
        </div>
        <div className="metric">
          <span className="label">Health</span>
          <span className="value">
            {healthFailing ? (
              <span className="badge failing">
                FAIL · {Math.ceil(status?.health_fail_remaining_s ?? 0)}s
              </span>
            ) : (
              <span className="badge running">OK</span>
            )}
          </span>
        </div>
      </div>

      <div className="status-panel">
        <h3>Active scenarios</h3>
        {scenarios.length === 0 ? (
          <div className="empty">No scenarios running.</div>
        ) : (
          <div className="scenarios-list">
            {scenarios.map((s) => (
              <div key={s.name} className="item">
                <span>{s.name}</span>
                <span>
                  {s.remaining_s !== null && s.remaining_s !== undefined
                    ? `${s.remaining_s.toFixed(0)}s left`
                    : 'running'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {log && <div className="log" style={{ marginBottom: 16 }}>{log}</div>}

      <div className="grid">
        <ScenarioCard
          title="CPU spike"
          description="Pin N threads at 100% for a fixed duration."
          activeNames={['cpu.spike']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Duration (s)" value={cpuSpikeDur} onChange={setCpuSpikeDur} min={1} />
            <NumberField label="Workers" value={cpuSpikeW} onChange={setCpuSpikeW} min={1} />
          </div>
          <div className="row">
            <button onClick={() => run('cpu.spike', () => api.cpuSpike(cpuSpikeDur, cpuSpikeW))}>
              Start
            </button>
            <button className="secondary" onClick={() => run('cpu.stop', api.cpuStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="CPU oscillation"
          description="Sine-wave duty cycle so CPU rises/falls every period."
          activeNames={['cpu.oscillate']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Period (s)" value={cpuOscPeriod} onChange={setCpuOscPeriod} min={1} />
            <NumberField label="Duration (s)" value={cpuOscDur} onChange={setCpuOscDur} min={1} />
            <NumberField label="Workers" value={cpuOscW} onChange={setCpuOscW} min={1} />
          </div>
          <div className="row">
            <button
              onClick={() =>
                run('cpu.oscillate', () => api.cpuOscillate(cpuOscPeriod, cpuOscDur, cpuOscW))
              }
            >
              Start
            </button>
            <button className="secondary" onClick={() => run('cpu.stop', api.cpuStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Memory grow + hold"
          description="Allocate MB of bytearray and hold it for hold_s."
          activeNames={['memory.grow']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Size (MB)" value={memGrowMb} onChange={setMemGrowMb} min={1} />
            <NumberField label="Hold (s)" value={memGrowHold} onChange={setMemGrowHold} min={1} />
          </div>
          <div className="row">
            <button onClick={() => run('memory.grow', () => api.memoryGrow(memGrowMb, memGrowHold))}>
              Start
            </button>
            <button className="secondary" onClick={() => run('memory.stop', api.memoryStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Memory oscillation"
          description="Grow/shrink between min and max MB cyclically."
          activeNames={['memory.oscillate']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Min (MB)" value={memMin} onChange={setMemMin} min={1} />
            <NumberField label="Max (MB)" value={memMax} onChange={setMemMax} min={1} />
            <NumberField label="Period (s)" value={memPeriod} onChange={setMemPeriod} min={2} />
            <NumberField label="Duration (s)" value={memDur} onChange={setMemDur} min={1} />
          </div>
          <div className="row">
            <button
              onClick={() =>
                run('memory.oscillate', () => api.memoryOscillate(memMin, memMax, memPeriod, memDur))
              }
            >
              Start
            </button>
            <button className="secondary" onClick={() => run('memory.stop', api.memoryStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Network egress (download)"
          description="Stream a large file from a public URL N times."
          activeNames={['network.egress']}
          scenarios={scenarios}
        >
          <div className="fields">
            <TextField
              label="URL (blank = default 100MB)"
              value={netUrl}
              onChange={setNetUrl}
              placeholder="https://speed.hetzner.de/100MB.bin"
            />
            <NumberField label="Repeat" value={netRepeat} onChange={setNetRepeat} min={1} max={20} />
          </div>
          <div className="row">
            <button onClick={() => run('network.egress', () => api.networkEgress(netUrl, netRepeat))}>
              Start
            </button>
            <button className="secondary" onClick={() => run('network.stop', api.networkStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Network oscillation"
          description="Periodic egress bursts every period_s for duration_s."
          activeNames={['network.oscillate']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Period (s)" value={netOscPeriod} onChange={setNetOscPeriod} min={2} />
            <NumberField label="Duration (s)" value={netOscDur} onChange={setNetOscDur} min={1} />
            <TextField label="URL (blank = default)" value={netUrl} onChange={setNetUrl} />
          </div>
          <div className="row">
            <button
              onClick={() =>
                run('network.oscillate', () => api.networkOscillate(netOscPeriod, netOscDur, netUrl))
              }
            >
              Start
            </button>
            <button className="secondary" onClick={() => run('network.stop', api.networkStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Network ingress (upload)"
          description="Browser POSTs a payload of N MB to /api/network/ingress."
          activeNames={[]}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField
              label="Payload (MB)"
              value={netIngressMb}
              onChange={setNetIngressMb}
              min={1}
              max={500}
            />
          </div>
          <div className="row">
            <button onClick={() => run('network.ingress', () => api.networkIngress(netIngressMb))}>
              Send
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Disk I/O"
          description="Write & fsync temp files (N MB × iterations), then delete."
          activeNames={['disk.io']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Size per file (MB)" value={diskMb} onChange={setDiskMb} min={1} />
            <NumberField label="Iterations" value={diskIter} onChange={setDiskIter} min={1} />
          </div>
          <div className="row">
            <button onClick={() => run('disk.io', () => api.diskIO(diskMb, diskIter))}>Start</button>
            <button className="secondary" onClick={() => run('disk.stop', api.diskStop)}>
              Stop
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Health check failure"
          description="Make /health return 500 for N seconds (triggers Embr auto-restore after ~3 minutes)."
          activeNames={['health.fail']}
          scenarios={scenarios}
        >
          <div className="fields">
            <NumberField label="Fail duration (s)" value={healthDur} onChange={setHealthDur} min={1} max={300} />
          </div>
          <div className="row">
            <button className="warning" onClick={() => run('health.fail', () => api.healthFail(healthDur))}>
              Trip health
            </button>
          </div>
        </ScenarioCard>

        <ScenarioCard
          title="Crash process"
          description="Calls os._exit(1) after a 1s delay — Embr should restore the sandbox."
          activeNames={[]}
          scenarios={scenarios}
        >
          <div className="row">
            <button className="danger" onClick={() => run('crash', api.crash)}>
              Crash
            </button>
          </div>
        </ScenarioCard>
      </div>
    </div>
  );
}
