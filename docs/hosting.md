# Free hosting

## Chosen: Koyeb

Adem's Render deploy hit an OOM before the nodes-cache fix existed, and he'd
rather not go back - reasonable, no need to relitigate it. Koyeb is a real
lateral move, not a downgrade: same Docker-native model as Render (builds
straight from the repo's `Dockerfile` via its Git-driven deploy, no code
changes needed beyond what's already there for Render), genuinely free tier,
no card required.

- 1 free web service, 0.1 vCPU, 512MB RAM, 2GB SSD
- Builds directly from a connected GitHub repo, auto-detects the root
  `Dockerfile` (same as Render's flow)
- Also injects its own `PORT` env var at runtime - the `Dockerfile`'s
  `CMD uvicorn ... --port ${PORT:-8000}` already handles this, same fix
  that was made for Render
- Supports a per-port health check the same way Render does

Also considered and ruled out (checked 2026-08-06): GitHub Pages is static-
only, cannot run a Python backend at all - a hard wall, not a preference.
Netlify's free tier is serverless-functions-first (Node/Go), doesn't build
from a Dockerfile, and doesn't fit this app's single persistent process with
in-memory startup state. Cloudflare's Containers product (the piece that
would actually work) requires the $5/month Workers Paid plan - no free tier
covers it. Vercel has the same serverless/no-Dockerfile mismatch as Netlify.
Earlier-ruled-out platforms unchanged: Railway's free tier is gutted to
~$1/month credit, Fly.io has no free tier and requires a card, Hugging Face
Spaces' Docker SDK is paid-only, Google Cloud Run needs a card and more GCP
setup than this project warrants, Back4App's 256MB is too tight.

Render is still a fallback worth knowing about: the OOM root cause is fixed
(see the nodes-cache entry in `docs/decisions.md`, 2026-08-06) and it hasn't
actually been retried with that fix - if Koyeb's cold starts or region
latency ever become a problem, Render remains a one-click retry, not a dead
end. Steps are below in case that's ever useful.

## Drop Ollama for the hosted deployment

None of the free tiers above have anywhere near enough RAM to run even a
small local model - that's a laptop/desktop-only piece of this project, not
something to bring to a free host. This isn't a loss for the hosted
deployment: Auto mode already prefers Groq (the cloud API) first as of
2026-08-06, and the deterministic template answer is always the fallback
if Groq is unreachable. So the hosted version only needs `docker-compose.yml`'s
`ollama` service deployed - just the `app` service, built from the root
`Dockerfile`, with `GROQ_API_KEY` set as an environment variable.

## Deploy steps (Koyeb)

1. Push this repo to GitHub if it isn't already.
2. On Koyeb: create a Service -> GitHub deployment method -> select the repo
   and branch (`main`).
3. Builder: choose **Dockerfile** (not a buildpack) - Koyeb auto-detects it
   at the repo root, same as Render.
4. Health check path: `/api/health` (same endpoint used for Render and for
   the local `docker-compose` healthcheck).
5. Environment Variables: add `GROQ_API_KEY` with the real key. Never commit
   `.env` to the repo - this is exactly why the key lives in the platform's
   dashboard instead.
6. Port: leave it to Koyeb's default/`PORT` injection - no manual override
   needed, the `Dockerfile`'s `CMD` already reads `${PORT:-8000}`.
7. Deploy. First build takes a few minutes (npm install + vite build + pip
   install, per the Dockerfile's layer order).

## Deploy steps (Render, fallback)

1. Push this repo to GitHub if it isn't already.
2. On Render: New -> Web Service -> connect the GitHub repo.
3. Environment: Docker - auto-detects the root `Dockerfile`.
4. Health Check Path: `/api/health`.
5. Environment Variables: add `GROQ_API_KEY`.
6. Leave the port field alone - Render injects its own `PORT`.
7. Deploy.

## Known gap

Neither the `Dockerfile`'s `${PORT:-8000}` change nor the nodes-cache build
step (`RUN python scripts/build_nodes_cache.py`) has been build-tested with
a real `docker build` - no `docker` binary is available in this sandbox, so
both were validated by review, direct measurement (the cache round-trips
losslessly, confirmed against the live parse), and the full test suite.
Trust the platform's own build log the first time you deploy, on whichever
platform you pick.
