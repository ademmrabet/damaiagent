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

export async function askQuestion(question, llm, previousNodeId, targetLanguage) {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      llm,
      previous_node_id: previousNodeId ?? null,
      // "auto" (the default) tells the backend to keep detecting the
      // answer language from the question itself - anything else is
      // an explicit override from the language picker (see
      // LanguagePicker.jsx, docs/decisions.md 2026-09-03).
      target_language: targetLanguage ?? 'auto',
    }),
  });
  return res.json();
}

export async function getDashboardSummary() {
  const res = await fetch('/api/dashboard/summary');
  if (!res.ok) throw new Error('dashboard summary unavailable');
  return res.json();
}
