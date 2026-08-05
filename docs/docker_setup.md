# Running the DAM agent with Docker (for sending to the professor)

This packages the whole app so it runs identically on any laptop with
Docker installed - no Python version mismatches, no "pip install the
right things in the right order," none of the setup friction from
running it bare-metal. Two containers:

- **`app`** - the FastAPI backend + chat UI + dashboard (this project's
  own code).
- **`ollama`** - the official Ollama image, for the local LLM mode.
  Kept as its own container rather than bundled into the app image,
  because that's what it actually is: a separate service with its own
  large model weights, not part of this project's code.

Groq needs no container - it's a cloud API, reached over the network
like any other.

The `app` image now also builds the React frontend (`webapp/frontend/`)
as part of `docker compose up --build` - a Node stage compiles it, then
only the built static output gets copied into the final Python image
(see the Dockerfile - Node itself never ships in the image that
actually runs). Nothing extra to do here versus before the frontend
rewrite; this is just why the first build takes a little longer now.

## One-time setup

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   (Windows/Mac/Linux all work the same way from here on).
2. In the project folder, create your env file from the template:
   ```
   cp .env.example .env
   ```
   Skip this if you're only going to use "No LLM" or "Ollama" mode -
   `.env` is optional, only needed for a real `GROQ_API_KEY`.

## Running it

```
docker compose up --build
```

First run takes a few minutes (downloading the Python and Ollama base
images, installing dependencies). After that, `docker compose up`
alone is fast. Once you see the app container log
`Application startup complete`, open **http://localhost:8000**.

> The log line right above that says `Uvicorn running on
> http://0.0.0.0:8000` - don't paste that address into your browser.
> `0.0.0.0` there means "listening on every network interface inside
> the container," not a real address to connect to; a browser given
> `0.0.0.0:8000` will fail with `ERR_ADDRESS_INVALID`. Always use
> `localhost:8000` (or whatever host port you mapped it to).

To stop: `Ctrl+C`, or `docker compose down` from another terminal.

## Enabling local (Ollama) mode

The `ollama` container starts empty - no model downloaded yet. Pull
one once (this persists in a Docker volume, so it's a one-time step,
not a one-time-per-run step):

```
docker compose exec ollama ollama pull llama3.1
```

That's a multi-GB download - do it well before the meeting, not in
the room. After it finishes, "Ollama (local)" and "Auto" mode both
work, and work fully offline from then on (no internet needed at demo
time for the local model - only Groq needs a live connection).

## Enabling Groq (API) mode

Put a real key in `.env` (see `docs/llm_setup.md` for how to get one):
```
GROQ_API_KEY=gsk_your_real_key_here
```
Then restart: `docker compose up` (no `--build` needed, env vars are
picked up fresh each start).

## Sending this to the professor

Everything needed is in this project folder plus Docker Desktop on
their machine - no separate install steps, no matching Python
versions. If Groq access isn't needed for their run, they can skip
the `.env` step entirely and just use "No LLM" or pull an Ollama model
themselves. Hand them this file (`docs/docker_setup.md`) alongside the
project folder.

## Troubleshooting

- **Port 8000 already in use**: something else on their machine is
  using it. Change the left-hand side of `"8000:8000"` in
  `docker-compose.yml` (e.g. `"8080:8000"`) and open that port instead.
- **`docker compose` not found**: older Docker installs use
  `docker-compose` (with a hyphen) as a separate command - try that
  instead.
- **Ollama mode says unavailable**: the model probably hasn't been
  pulled yet in this environment - rerun the `ollama pull` step above.
- **`pip install` fails during `docker compose up --build`**: unlikely
  (every dependency here ships prebuilt wheels for standard
  Windows/Mac/Linux Docker setups), but if it happens on an unusual
  machine architecture, change `FROM python:3.11-slim` to
  `FROM python:3.11` in the `Dockerfile` and rebuild - the full image
  includes compilers or the rare cases that need to build a package
  from source instead of using a prebuilt wheel.
