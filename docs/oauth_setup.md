# Setting up Google and Microsoft sign-in

Email/password login works with zero setup - signup and login are live
as soon as `JWT_SECRET_KEY` and (optionally) `DATABASE_URL` are set (see
below). Everything in this doc is only needed to also enable the
"Sign in with Google" and "Sign in with Microsoft" buttons.

Both are registered lazily (`webapp/oauth.py`): if a provider's client
ID/secret aren't set, its login button's endpoint returns a clean 503
instead of crashing the app, so you can ship email/password first and
add either provider later without touching code again.

## Required either way

```
cp .env.example .env
```

Then in `.env`, generate and set a real secret:

```
JWT_SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_hex(32))">
```

And point `DATABASE_URL` at a real Postgres instance once you're ready
to deploy (see "Choosing a database" below) - leave it unset for local
development and it falls back to a SQLite file automatically.

## Choosing a database

Render's own free tier has **no persistent disk**. If `DATABASE_URL` is
left pointing at a SQLite file in production, every redeploy silently
wipes every registered user - the same class of bug already hit once
in this project (the Render OOM crash fixed by caching nodes at build
time). Two free options that actually persist:

- **Neon** (https://neon.tech) - free serverless Postgres, no
  auto-deletion. Create a project, copy the connection string it gives
  you (starts with `postgresql://`), paste it into `DATABASE_URL`.
- **Supabase** (https://supabase.com) - also free, includes a Postgres
  connection string under Project Settings → Database.

Either works identically from the app's side - `webapp/db.py` doesn't
care which one is behind the URL.

## Option A - Google

1. Go to https://console.cloud.google.com and create a project (or
   reuse an existing one).
2. **APIs & Services → OAuth consent screen**: choose **External**,
   fill in the app name (e.g. "DAM AI Agent") and your email, save.
   You do not need to submit it for verification to use it yourself or
   with a handful of test users - Google will just show an "unverified
   app" warning screen that you click through.
3. **APIs & Services → Credentials → Create Credentials → OAuth client
   ID**. Application type: **Web application**.
4. Under **Authorized redirect URIs**, add both:
   - `http://localhost:8000/api/auth/google/callback` (local dev)
   - `https://<your-render-app>.onrender.com/api/auth/google/callback`
     (production - use your actual Render URL)
5. Save. Copy the **Client ID** and **Client secret** it gives you into
   `.env`:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

## Option B - Microsoft (Entra ID)

1. Go to https://entra.microsoft.com (or portal.azure.com → Microsoft
   Entra ID) and sign in with any Microsoft account - a personal one is
   fine for development.
2. **App registrations → New registration**. Name it (e.g. "DAM AI
   Agent"). Under **Supported account types**, choose "Accounts in any
   organizational directory and personal Microsoft accounts" unless you
   specifically want to restrict sign-in to AfDB's own tenant only.
3. Under **Redirect URI**, platform **Web**, add:
   - `http://localhost:8000/api/auth/microsoft/callback` (local dev)
   - `https://<your-render-app>.onrender.com/api/auth/microsoft/callback`
     (production)
4. After creation, copy the **Application (client) ID** from the
   Overview page into `.env` as `MICROSOFT_CLIENT_ID`.
5. **Certificates & secrets → New client secret**. Copy the secret
   **value** (not the ID) immediately - it's only shown once. Set it as
   `MICROSOFT_CLIENT_SECRET`.
6. If you chose "any organizational directory" in step 2, leave
   `MICROSOFT_TENANT_ID=common` (the default). If you restricted it to
   AfDB's own tenant specifically, set `MICROSOFT_TENANT_ID` to that
   tenant's ID instead (found on the Entra ID Overview page).

## Setting `BACKEND_BASE_URL` in production

The backend builds its own OAuth redirect URIs from this variable, so
it must match your actual deployed URL exactly (no trailing slash):

```
BACKEND_BASE_URL=https://<your-render-app>.onrender.com
```

Locally, the default (`http://localhost:8000`) already matches the
redirect URIs registered above, so nothing needs to be set for local
testing.

## Verifying it worked

With everything set, restart the backend and hit either login route
directly in a browser:

- `http://localhost:8000/api/auth/google/login`
- `http://localhost:8000/api/auth/microsoft/login`

Each should redirect to the provider's real consent screen instead of
returning `{"detail": "... is not configured yet"}`. After granting
consent, you should land back on `/login?token=<a long JWT>` - proof
the whole round trip (redirect out, callback, user creation, token
issuance) completed.
