# Wandr

Wandr is a trip-planning app that turns a destination (or a free-text brief) into a scored itinerary: ranked stays/food/activities/attractions, a day-by-day plan, and a budget breakdown. It ships with a curated catalog for four cities and an optional AI planning agent that can resolve destinations and interests outside that catalog from a natural-language brief.

## Architecture

```
wandr/
├── backend/            FastAPI service (Python 3.12)
│   ├── app/
│   │   ├── main.py             FastAPI app, CORS, /health
│   │   ├── config.py           pydantic-settings (.env-driven)
│   │   ├── routes/trips.py     /api/trips endpoints
│   │   ├── schemas/trip.py     Pydantic request/response models
│   │   ├── services/
│   │   │   ├── destination_resolver.py  catalog lookup, aliases, agent handoff
│   │   │   ├── trip_engine.py           scoring, filtering, itinerary building
│   │   │   ├── ai_personalization.py    narrative blurb generator
│   │   │   ├── persistence.py           SQLite-backed saved trips
│   │   │   ├── agent/planning.py        Groq / Azure OpenAI / Anthropic planning agent
│   │   │   └── research/                live destination research (Google Places)
│   │   └── data/destinations.py         curated catalog (Kyoto, Lisbon, Jaipur, Kuala Lumpur)
│   └── tests/           pytest suite
├── frontend/            React + Vite SPA
│   └── src/App.jsx      planner form, results view, saved trips
└── Makefile             install / run / test shortcuts
```

## How a trip request flows

1. The frontend posts a `TripRequest` to `POST /api/trips/plan` (destination, dates, travelers, persona, budget, travel style, interests, and optionally a free-text `brief` with `agent_decides: true`).
2. `destination_resolver.resolve_destination` resolves the destination:
   - exact match in the curated catalog,
   - known alias/text-hint match (e.g. "Malaysia" → Kuala Lumpur),
   - or, if `agent_decides` is set and an AI provider is configured, hands the brief to the **planning agent**, which returns a structured destination decision (and, for cities outside the catalog, four researched candidate places).
3. `trip_engine.plan_trip` scores every candidate against persona weights, interest tags, travel-style tags, and budget fit, ranks them, and builds a day-by-day itinerary respecting the style's pacing rules.
4. `ai_personalization.generate_personalization` produces a short narrative summary for the trip.
5. The response (`TripResponse`) includes recommendations, itinerary, budget breakdown, currency, and metadata about how the destination was resolved (catalog / alias / text_hint / agent, with confidence and rationale).
6. Trips can be saved/listed/deleted via `/api/trips/save`, `/api/trips/saved`, `/api/trips/saved/{id}` — persisted to a local SQLite database (`backend/wandr.db`).

## API

Base path: `/api` (see `backend/app/config.py`)

| Method | Path                    | Description                        |
|--------|-------------------------|-------------------------------------|
| POST   | `/trips/plan`           | Generate a trip plan                |
| POST   | `/trips/save`           | Save a generated trip               |
| GET    | `/trips/saved`          | List saved trips                    |
| GET    | `/trips/saved/{id}`     | Fetch one saved trip                |
| DELETE | `/trips/saved/{id}`     | Delete a saved trip                 |
| GET    | `/health`               | Service health check                |

Interactive docs are available at `http://127.0.0.1:8001/docs` while the backend is running (FastAPI's auto-generated Swagger UI).

## AI / research integrations (optional)

These are only used when `agent_decides: true` is sent and credentials are configured in `.env`:

- **Planning agent** — resolves free-text briefs into a destination + persona/budget/style/interests. Prefers **Groq** (free tier) if `GROQ_API_KEY` is set; otherwise falls back to **Azure OpenAI** if `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_DEPLOYMENT` are all set; otherwise falls back to **Anthropic** if `ANTHROPIC_API_KEY` is set. If none are configured, agent-based resolution is disabled and requests fall back to catalog/alias matching.
- **Destination research** (`services/research/`) — for destinations outside the catalog, can look up live places via the Google Places API (`GOOGLE_MAPS_API_KEY`) to build candidate recommendations.

Without any of these keys set, the app runs fully on the local catalog (Kyoto, Lisbon, Jaipur, Kuala Lumpur).

## Setup

Prerequisites: Python 3.12+, Node.js (for the frontend), `make`.

```bash
# 1. Install backend dependencies (creates .venv, installs requirements.txt)
make install

# 2. Configure environment (optional — only needed for AI/research features)
cp .env.example .env
# then fill in ANTHROPIC_API_KEY or the AZURE_OPENAI_* values, and/or GOOGLE_MAPS_API_KEY

# 3. Install frontend dependencies
npm --prefix frontend install
```

## Running locally

```bash
# Backend — http://127.0.0.1:8001 (reads PORT to override)
make backend-up      # or: make run

# Frontend — http://127.0.0.1:5173
make frontend-up
```

The frontend reads `VITE_API_URL` (defaults to `http://127.0.0.1:8001`) to reach the backend — see `frontend/src/App.jsx`.

Other Makefile targets:

```bash
make backend-down    # stop whatever is listening on PORT (default 8001)
make frontend-build  # production build of the frontend (frontend/dist)
make test            # run the backend pytest suite
```

## Testing

```bash
make test
```

Covers destination resolution (catalog/alias/agent), the Malaysia→Kuala Lumpur alias and currency handling, trip persistence, the AI personalization narrative, the trip request/response contract, and trip-engine scoring/itinerary behavior (`backend/tests/`).

## Configuration reference

All settings live in `backend/app/config.py` and are loaded from `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` / `GROQ_MODEL` | Groq planning agent (free tier, checked first when set) |
| `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_DEPLOYMENT` / `AZURE_OPENAI_API_VERSION` | Azure OpenAI planning agent (used when Groq isn't configured) |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` / `ANTHROPIC_API_VERSION` | Anthropic fallback planning agent |
| `AGENT_TIMEOUT_SECONDS` / `AGENT_MIN_CONFIDENCE` | Planning agent request timeout and minimum acceptable confidence |
| `GOOGLE_MAPS_API_KEY` / `GOOGLE_PLACES_BASE_URL` | Live destination research for cities outside the catalog |
| `RESEARCH_TIMEOUT_SECONDS` / `RESEARCH_MAX_RESULTS` / `RESEARCH_CACHE_TTL_SECONDS` | Research request tuning |

`database_url` and `api_prefix` are also configurable but default to `sqlite:///./wandr.db` and `/api` respectively; the SQLite persistence layer (`services/persistence.py`) currently connects directly to `backend/wandr.db` rather than parsing `database_url`.
