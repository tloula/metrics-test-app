export type Status = {
  now: number;
  scenarios: Array<{
    name: string;
    started_at: number;
    ends_at: number | null;
    remaining_s: number | null;
    params: Record<string, unknown>;
    detail: Record<string, unknown>;
  }>;
  process?: {
    pid: number;
    cpu_percent: number;
    rss_bytes: number;
    num_threads: number;
  };
  system?: {
    cpu_percent: number;
    memory_total_bytes: number;
    memory_used_bytes: number;
    memory_available_bytes: number;
  };
  network?: { rx_bytes: number; tx_bytes: number };
  health_fail_remaining_s?: number;
};

async function call<T = unknown>(
  path: string,
  body?: unknown,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    method: body === undefined && !init?.method ? 'GET' : 'POST',
    headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...init,
  });
  const text = await res.text();
  let json: unknown = text;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* ignore */
  }
  if (!res.ok) {
    throw new Error(`${res.status}: ${typeof json === 'string' ? json : JSON.stringify(json)}`);
  }
  return json as T;
}

export const api = {
  status: () => call<Status>('/api/status'),
  cpuSpike: (duration_s: number, workers: number) =>
    call('/api/cpu/spike', { duration_s, workers }),
  cpuOscillate: (period_s: number, duration_s: number, workers: number) =>
    call('/api/cpu/oscillate', { period_s, duration_s, workers }),
  cpuStop: () => call('/api/cpu/stop', {}),
  memoryGrow: (mb: number, hold_s: number) => call('/api/memory/grow', { mb, hold_s }),
  memoryOscillate: (min_mb: number, max_mb: number, period_s: number, duration_s: number) =>
    call('/api/memory/oscillate', { min_mb, max_mb, period_s, duration_s }),
  memoryStop: () => call('/api/memory/stop', {}),
  networkEgress: (url: string, repeat: number) => call('/api/network/egress', { url, repeat }),
  networkOscillate: (period_s: number, duration_s: number, url: string) =>
    call('/api/network/oscillate', { period_s, duration_s, url }),
  networkStop: () => call('/api/network/stop', {}),
  networkIngress: async (sizeMb: number) => {
    const bytes = new Uint8Array(sizeMb * 1024 * 1024);
    // Fill with non-zero so compression-aware proxies still see real bytes.
    for (let i = 0; i < bytes.length; i += 4096) bytes[i] = (i & 0xff) || 1;
    return call('/api/network/ingress', undefined, {
      method: 'POST',
      body: bytes,
      headers: { 'content-type': 'application/octet-stream' },
    });
  },
  diskIO: (mb: number, iterations: number) => call('/api/disk/io', { mb, iterations }),
  diskStop: () => call('/api/disk/stop', {}),
  healthFail: (duration_s: number) => call('/api/health/fail', { duration_s }),
  crash: () =>
    call('/api/crash?confirm=yes', undefined, {
      method: 'POST',
    }),
  stopAll: () => call('/api/stop/all', {}),
};
