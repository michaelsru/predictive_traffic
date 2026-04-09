export const fetchStatus = async () => {
  const res = await fetch('/api/status');
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
};

export const fetchSimulatorStatus = async () => {
  const res = await fetch('/api/simulator/status');
  if (!res.ok) throw new Error('Failed to fetch simulator status');
  return res.json();
};

export const controlSimulator = async (action) => {
  const res = await fetch(`/api/simulator/${action}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to ${action} simulator`);
  return res.json();
};

export const fetchHistory = async (seg, limit = 30) => {
  const res = await fetch(`/api/history/${seg}?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
};

export const setScenario = async (mode) => {
  const res = await fetch(`/api/scenario/${mode}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to set scenario');
  return res.json();
};

export const sendChat = async (message, history) => {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history })
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const body = await res.json(); detail = body.detail ?? detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
};

export const fetchIncidents = async ({ limit = 50, offset = 0, segment_id } = {}) => {
  const params = new URLSearchParams({ limit, offset });
  if (segment_id) params.set('segment_id', segment_id);
  const res = await fetch(`/api/incidents?${params}`);
  if (!res.ok) throw new Error('Failed to fetch incidents');
  return res.json();
};

export const fetchReadings = async ({ limit = 100, offset = 0, segment_id, min_severity } = {}) => {
  const params = new URLSearchParams({ limit, offset });
  if (segment_id)   params.set('segment_id', segment_id);
  if (min_severity) params.set('min_severity', min_severity);
  const res = await fetch(`/api/readings?${params}`);
  if (!res.ok) throw new Error('Failed to fetch readings');
  return res.json();
};

export const logIncident = async (payload) => {
  const res = await fetch('/api/incident', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const body = await res.json(); detail = body.detail ?? detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
};export const fetchAlertLogs = async ({ limit = 100, offset = 0, segment_id } = {}) => {
  const params = new URLSearchParams({ limit, offset });
  if (segment_id) params.set('segment_id', segment_id);
  const res = await fetch(`/api/alert-logs?${params}`);
  if (!res.ok) throw new Error('Failed to fetch alert logs');
  return res.json();
};
