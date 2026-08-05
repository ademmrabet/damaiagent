# ---- stage 1: build the React frontend ----
# Separate stage so the final image never needs Node/npm at all - only
# the built static output (webapp/static/) gets copied into stage 2.
# This stage's whole filesystem, including node_modules, is discarded
# once the build finishes.
FROM node:20-slim AS frontend-build

WORKDIR /app/webapp/frontend

# package*.json first, own layer - same "don't reinstall everything
# just because a .jsx file changed" reasoning as the pip layer below.
COPY webapp/frontend/package*.json ./
RUN npm install

COPY webapp/frontend/ ./
RUN npm run build
# Vite's outDir (vite.config.js) points at ../static, so this leaves
# the built landing.html / chat.html / dashboard.html / assets/ at
# /app/webapp/static inside this stage.


# ---- stage 2: the actual app ----
FROM python:3.11-slim

WORKDIR /app

# Dependencies in their own layer so a code-only change doesn't force
# a full pip reinstall on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-parses the raw PDF once, here at build time, and caches the
# result to data/processed/nodes.json (see scripts/build_nodes_cache.py).
# webapp/backend.py's startup event loads this cache instead of
# re-running pdfplumber on every container boot - re-parsing at runtime
# was heavy enough (word + character extraction across every page) to
# OOM-kill the container on Render's 512MB free tier before it ever
# opened a port. Build-time environments generally have more headroom
# than a constrained free runtime instance, and this only needs to run
# once per image build, not once per boot.
RUN python scripts/build_nodes_cache.py

# Overwrites the (gitignored, so possibly-empty-or-stale) webapp/static
# from the repo copy above with the real build output. Ordered last so
# it always wins regardless of what COPY . . picked up.
COPY --from=frontend-build /app/webapp/static ./webapp/static

EXPOSE 8000

# 0.0.0.0, not 127.0.0.1 - the app must accept connections from
# outside the container (through the port mapping), not just from
# itself. Binding to 127.0.0.1 here is a common Docker mistake that
# makes a container's server unreachable from the host entirely.
#
# Shell form (not the JSON-array form used before) so ${PORT:-8000}
# actually gets expanded - most free container hosts (Render, Railway,
# Cloud Run, Koyeb...) inject their own PORT env var at deploy time and
# expect the app to bind to it, rather than a fixed port the platform
# chose for you. Defaults to 8000 when PORT isn't set (bare `docker
# run`, docker-compose here) so local behavior is unchanged.
CMD uvicorn webapp.backend:app --host 0.0.0.0 --port ${PORT:-8000}
