import { useEffect, useState } from 'react';
import { getToken, isLoggedIn, login, setToken, signup } from '../api.js';
import './login.css';

// Only ever redirects back into the app's own /chat page (which is
// where a "Share via QR code" link points - see Chat.jsx and
// webapp/backend.py's /api/conversations/shared/{token}/claim) -
// never an arbitrary URL, so a crafted ?redirect= query param can't
// be used to bounce a freshly-authenticated user off to another site.
function getRedirectTarget() {
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get('redirect');
  if (redirect && redirect.startsWith('/chat')) return redirect;
  return '/chat';
}

export default function Login() {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthToken = params.get('token');

    if (oauthToken) {
      setToken(oauthToken);
      window.location.replace('/chat');
      return;
    }

    if (isLoggedIn() && getToken()) {
      window.location.replace(getRedirectTarget());
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = mode === 'login' ? await login(email, password) : await signup(email, password, name);
      setToken(result.access_token);
      window.location.href = getRedirectTarget();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <span className="login-badge">Delegation of Authority Matrix</span>
        <h1>DAM AI Agent</h1>
        <p className="login-subtitle">
          {mode === 'login' ? 'Sign in to continue.' : 'Create an account to get started.'}
        </p>

        <div className="oauth-buttons">
          <a className="oauth-btn oauth-google" href="/api/auth/google/login">
            <span className="oauth-icon" aria-hidden="true">
              G
            </span>
            Continue with Google
          </a>
          <a className="oauth-btn oauth-microsoft" href="/api/auth/microsoft/login">
            <span className="oauth-icon" aria-hidden="true">
              ⊞
            </span>
            Continue with Microsoft
          </a>
        </div>

        <div className="login-divider">
          <span>or</span>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                placeholder="Optional"
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={mode === 'signup' ? 8 : undefined}
              required
            />
          </label>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-submit" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="login-switch">
          {mode === 'login' ? (
            <>
              Don&rsquo;t have an account?{' '}
              <button type="button" onClick={() => setMode('signup')}>
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button type="button" onClick={() => setMode('login')}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
