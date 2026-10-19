# stage 1: build the react frontend
FROM node:20-slim AS frontend-build

WORKDIR /app/webapp/frontend

COPY webapp/frontend/package*.json ./
RUN npm install

COPY webapp/frontend/ ./
RUN npm run build

# stage 2: the app itself
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# parse the pdf once at build time
RUN python scripts/build_nodes_cache.py

COPY --from=frontend-build /app/webapp/static ./webapp/static

EXPOSE 8000

# bind 0.0.0.0 and honour the host's PORT
CMD uvicorn webapp.backend:app --host 0.0.0.0 --port ${PORT:-8000}
