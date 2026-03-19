export const fetchStatus = async () => {
  const res = await fetch('/api/status');
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
};

export const fetchHistory = async (seg) => {
  const res = await fetch(`/api/history/${seg}`);
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
  if (!res.ok) throw new Error('Failed to send chat');
  return res.json();
};
