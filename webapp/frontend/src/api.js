export async function checkHealth() {
  const res = await fetch('/api/health', { cache: 'no-store' });
  if (!res.ok) throw new Error('unhealthy');
  return res.json();
}

export async function getLlmConfig() {
  const res = await fetch('/api/llm/config');
  if (!res.ok) throw new Error('llm config unavailable');
  return res.json();
}

export async function askQuestion(question, llm, previousNodeId) {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, llm, previous_node_id: previousNodeId ?? null }),
  });
  return res.json();
}

export async function getDashboardSummary() {
  const res = await fetch('/api/dashboard/summary');
  if (!res.ok) throw new Error('dashboard summary unavailable');
  return res.json();
}
