export const fetchStatus = async () => {
  const res = await fetch('/api/status');
  if (!res.ok) throw new Error('Failed to fetch status');
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
};

