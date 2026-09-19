const TOKEN_KEY = 'dam_token';

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function isLoggedIn() {
  return !!getToken();
}

export function logout() {
  clearToken();
  window.location.href = '/login';
}

async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    return new Promise(() => {});
  }
  return res;
}

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
  const res = await authFetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      llm,
      previous_node_id: previousNodeId ?? null,
      target_language: targetLanguage ?? 'auto',
    }),
  });
  return res.json();
}

export async function getDashboardSummary() {
  const res = await authFetch('/api/dashboard/summary');
  if (res.status === 403) throw new Error('forbidden');
  if (!res.ok) throw new Error('dashboard summary unavailable');
  return res.json();
}

export async function getCurrentUser() {
  const res = await authFetch('/api/auth/me');
  if (!res.ok) throw new Error('not authenticated');
  return res.json();
}

export async function signup(email, password, name) {
  const res = await fetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name: name || null }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || 'Signup failed');
  return body;
}

export async function login(email, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || 'Login failed');
  return body;
}
