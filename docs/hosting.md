# Free hosting

## Recommendation: Render

Render's free web-service tier is the best fit for this project specifically
because it's genuinely Docker-native - it builds straight from the repo's
`Dockerfile`, so the existing multi-stage build (Node build stage discarded,
Python runtime stage shipped) works with zero changes beyond the `$PORT` fix
below. No credit card required to sign up or deploy.

- 750 free instance-hours/month - enough for one service to run continuously
  all month, or comfortably enough for demo/grading use
- 512MB RAM - enough for FastAPI + the deterministic agent + Groq calls (no
  local model running here, see below)
- Free services sleep after 15 minutes of no inbound traffic, and take
  roughly 30-60 seconds to wake back up on the next request. This is the one
  real trade-off - **ping the app a minute or two before a live demo** so
  it's already warm when the professor is watching.

Alternatives considered and why they're worse fits right now (checked
2026-08-06): Railway's free tier was gutted to ~$1/month credit, not
actually free anymore. Fly.io dropped its free tier entirely and requires
a card just to deploy. Hugging Face Spaces' Docker SDK moved behind a paid
plan. Google Cloud Run is generous but requires a card and real GCP account
setup - more friction than this project needs. Back4App's 256MB RAM is too
tight for this stack. Koyeb is a legitimate secondary option (1 free
service, 0.1 vCPU / 512MB, no card) if Render's cold starts turn out to be a
problem for a specific demo window.

## Drop Ollama for the hosted deployment

None of the free tiers above have anywhere near enough RAM to run even a
small local model - that's a laptop/desktop-only piece of this project, not
something to bring to a free host. This isn't a loss for the hosted
deployment: Auto mode already prefers Groq (the cloud API) first as of
2026-08-06, and the deterministic template answer is always the fallback
if Groq is unreachable. So the hosted version only needs `docker-compose.yml`'s
`ollama` service deployed - just the `app` service, built from the root
`Dockerfile`, with `GROQ_API_KEY` set as an environment variable.

## Deploy steps (Render)

1. Push this repo to GitHub if it isn't already (Render deploys from a git
   remote, not a local folder).
2. On Render: New -> Web Service -> connect the GitHub repo.
3. Environment: Docker. Render will auto-detect the root `Dockerfile` - no
   build command needed, it just runs `docker build`.
4. Under Environment Variables, add `GROQ_API_KEY` with the real key.
   Never commit `.env` to the repo - this is exactly why the key lives in
   Render's dashboard instead.
5. Leave the port field alone / don't hardcode one - Render injects its own
   `PORT` env var at runtime, and the `Dockerfile`'s `CMD` now reads it
   (`--port ${PORT:-8000}`, falls back to 8000 only when `PORT` isn't set,
   e.g. local `docker-compose`).
6. Deploy. First build will take a few minutes (npm install + vite build +
   pip install, in that order per the Dockerfile's layer caching).

## Known gap

The `Dockerfile`'s `${PORT:-8000}` change hasn't been build-tested - no
`docker` binary is available in this sandbox, so this was validated by
review only (confirmed `docker-compose.yml` doesn't set `PORT` and its
healthcheck + port mapping are both hardcoded to `8000`, so local behavior
is unaffected either way). Worth a real `docker build` once on your own
machine, or just trust Render's own build log the first time you deploy.
