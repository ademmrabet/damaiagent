const TOKEN_KEY = 'dam_token';
// jwt kept in localStorage; helpers below read and clear it

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

async function parseJsonBody(res, fallbackMessage) {
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail = body && body.detail;
    throw new Error(detail || `${fallbackMessage} (server returned ${res.status})`);
  }
  return body;
}
// calls to the backend, one small function per endpoint

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

export async function askQuestion(question, llm, previousNodeId, targetLanguage, attachment) {
  const res = await authFetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      llm,
      previous_node_id: previousNodeId ?? null,
      target_language: targetLanguage ?? 'auto',
      attachment: attachment
        ? { key: attachment.key, content_type: attachment.content_type, filename: attachment.filename }
        : null,
    }),
  });
  return parseJsonBody(res, 'Failed to get an answer');
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
  return parseJsonBody(res, 'Signup failed');
}

export async function listConversations() {
  const res = await authFetch('/api/conversations');
  if (!res.ok) throw new Error('conversations unavailable');
  return res.json();
}

export async function createConversationApi() {
  const res = await authFetch('/api/conversations', { method: 'POST' });
  if (!res.ok) throw new Error('failed to create conversation');
  return res.json();
}

export async function getConversationApi(id) {
  const res = await authFetch(`/api/conversations/${id}`);
  if (!res.ok) throw new Error('failed to load conversation');
  return res.json();
}

export async function postConversationMessage(id, message) {
  const res = await authFetch(`/api/conversations/${id}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message),
  });
  if (!res.ok) throw new Error('failed to save message');
  return res.json();
}

export async function deleteConversationApi(id) {
  const res = await authFetch(`/api/conversations/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('failed to delete conversation');
  return res.json();
}

export async function shareConversationApi(id, email) {
  const res = await authFetch(`/api/conversations/${id}/share`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  return parseJsonBody(res, 'Failed to share conversation');
}

export async function unshareConversationApi(id, targetUserId) {
  const res = await authFetch(`/api/conversations/${id}/share/${targetUserId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('failed to unshare conversation');
  return res.json();
}

export async function createShareLinkApi(id) {
  const res = await authFetch(`/api/conversations/${id}/share-link`, { method: 'POST' });
  return parseJsonBody(res, 'Failed to create share link');
}

export async function revokeShareLinkApi(id) {
  const res = await authFetch(`/api/conversations/${id}/share-link`, { method: 'DELETE' });
  if (!res.ok) throw new Error('failed to revoke share link');
  return res.json();
}

export async function claimShareLinkApi(token) {
  const res = await authFetch(`/api/conversations/shared/${encodeURIComponent(token)}/claim`, {
    method: 'POST',
  });
  return parseJsonBody(res, 'This share link is invalid or has expired');
}
// sse can't send headers, so the token goes in the query string

export function openEventSource() {
  const token = getToken();
  if (!token) return null;
  return new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
}

export async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await authFetch('/api/uploads', { method: 'POST', body: formData });
  return parseJsonBody(res, 'Upload failed');
}
// encode each path segment but keep the slashes

export async function getAttachmentUrl(conversationId, key) {
  const encodedKey = key.split('/').map(encodeURIComponent).join('/');
  const res = await authFetch(`/api/conversations/${conversationId}/attachments/${encodedKey}`);
  const body = await parseJsonBody(res, 'Could not open attachment');
  return body.url;
}

export async function transcribeAudio(blob) {
  const formData = new FormData();
  formData.append('file', blob, 'clip.webm');
  const res = await authFetch('/api/transcribe', { method: 'POST', body: formData });
  const body = await parseJsonBody(res, 'Transcription failed');
  return body.text;
}

export async function login(email, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return parseJsonBody(res, 'Login failed');
}
