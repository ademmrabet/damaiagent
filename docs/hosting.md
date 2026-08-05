# Free hosting

## Recommendation: Render

The OOM that killed the first Render attempt is fixed (see the nodes-cache
entry in `docs/decisions.md`, 2026-08-06) - it just hadn't been retried yet.
Render remains the best fit: genuinely Docker-native, builds straight from
the repo's `Dockerfile`, no credit card required.

- 750 free instance-hours/month, 512MB RAM
- Free services sleep after 15 minutes of no inbound traffic, ~30-60s
  cold-start wake - **ping the app a minute or two before a live demo**.

Alternatives tried or considered, and why they don't fit (checked
2026-08-06): **Koyeb** is architecturally the right shape (Docker-native,
same model as Render) but was acquired by Mistral AI in Feb 2026 and is
mid-transition into "Mistral Compute" - the self-serve dashboard currently
shows a "stay tuned for a revamped experience" banner instead of a normal
create-service flow. Not worth trusting against a graded deadline; worth
revisiting later if the transition settles. **Vercel** ("FastAPI preset")
is serverless functions, not a persistent container - ignores the repo's
`Dockerfile` entirely, so neither the frontend build nor the nodes-cache
build step would run, and the app's single in-memory `state` dict has no
equivalent in a cold-start-per-invocation model. **GitHub Pages** is static
files only, by design - cannot execute Python at all, a hard wall not a
preference. **Netlify** has the same serverless/no-Dockerfile mismatch as
Vercel. **Cloudflare**'s Containers product (the piece that would actually
fit) requires the $5/month Workers Paid plan - no free tier covers it.
Earlier-ruled-out platforms unchanged: Railway's free tier is gutted to
~$1/month credit, Fly.io has no free tier and requires a card, Hugging Face
Spaces' Docker SDK is paid-only, Google Cloud Run needs a card and more GCP
setup than this project warrants, Back4App's 256MB is too tight.

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

1. Push this repo to GitHub if it isn't already.
2. On Render: New -> Web Service -> connect the GitHub repo.
3. Environment: Docker - auto-detects the root `Dockerfile`.
4. Health Check Path: `/api/health`.
5. Environment Variables: add `GROQ_API_KEY`.
6. Leave the port field alone - Render injects its own `PORT`.
7. If the service already exists from an earlier failed attempt, use
   **Manual Deploy -> Clear build cache & deploy**, not a plain retry - a
   plain retry can reuse cached layers from the old, OOM-ing build.
8. Deploy. First build takes a few minutes (npm install + vite build + pip
   install + the nodes-cache build step, per the Dockerfile's layer order).

## Known gap

Neither the `Dockerfile`'s `${PORT:-8000}` change nor the nodes-cache build
step (`RUN python scripts/build_nodes_cache.py`) has been build-tested with
a real `docker build` - no `docker` binary is available in this sandbox, so
both were validated by review, direct measurement (the cache round-trips
losslessly, confirmed against the live parse), and the full test suite.
Trust the platform's own build log the first time you deploy, on whichever
platform you pick.
