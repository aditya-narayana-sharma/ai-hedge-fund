# AI Hedge Fund - Backend [WIP] 🚧
This project is currently a work in progress.  To track progress, please get updates [here](https://x.com/virattt).

This is the backend server for the AI Hedge Fund project. It provides a simple REST API to interact with the AI Hedge Fund system, allowing you to run the hedge fund through a web interface.

## Overview

This backend project is a FastAPI application that serves as the server-side component of the AI Hedge Fund system. It exposes endpoints for running the hedge fund trading system and backtester.

This backend is designed to work with a future frontend application that will allow users to interact with the AI Hedge Fund system through their browser.

## Installation

### Using Poetry

1. Clone the repository:
```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

2. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install dependencies:
```bash
# From the root directory
poetry install
```

4. Set up your environment variables:
```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

5. Edit the .env file to add your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# For running LLMs hosted by groq (deepseek, llama3, etc.)
GROQ_API_KEY=your-groq-api-key

# For getting financial data to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

## Running the Server

To run the development server:

```bash
# Run from the REPOSITORY ROOT, not from app/backend.
# main.py imports `app.backend.routes`, so the root must be on sys.path;
# `cd app/backend && uvicorn main:app` makes `app` unresolvable and loads
# this module twice under two different names.
poetry run uvicorn app.backend.main:app --reload
```

This will start the FastAPI server with hot-reloading enabled.

The API will be available at:
- API Endpoint: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Welcome message |
| `GET` | `/ping` | Simple endpoint to test server connectivity |
| `GET` | `/agents` | Analyst catalog, derived from `ANALYST_CONFIG` |
| `GET` | `/models` | Model catalog, cloud providers and Ollama |
| `POST` | `/hedge-fund/run` | Run the AI Hedge Fund, streaming SSE |
| `POST` | `/backtest` | Day-by-day simulation, streaming SSE |

Both `POST` endpoints stream the same event envelope — `start`, `progress`*,
then `complete` or `error` — and every event carries the `run_id`, which is
also echoed in the `X-Run-Id` response header.

Set `AI_HEDGE_FUND_API_KEY` to require an `X-API-Key` header on the two run
endpoints, and `AI_HEDGE_FUND_RATE_LIMIT` to cap requests per client. Both are
disabled when unset. Interactive docs are at `/docs`.

## Project Structure

```
app/backend/
├── api/                      # Composition: which routers exist, and their guards
│   ├── deps.py               # API-key auth and rate limiting (both opt-in)
│   └── v1.py                 # Router assembly
├── database/                 # Optional run-history persistence
│   ├── models.py             # SQLAlchemy models
│   └── session.py            # Engine and session handling
├── models/                   # Domain models
│   ├── events.py             # SSE event envelope
│   └── schemas.py            # Request and response schemas
├── routes/                   # Endpoint implementations
│   ├── backtest.py           # POST /backtest
│   ├── catalog.py            # GET /agents, GET /models
│   ├── health.py             # GET /, GET /ping
│   └── hedge_fund.py         # POST /hedge-fund/run
├── services/                 # Business logic
│   ├── backtest.py           # Backtest orchestration and wire mapping
│   ├── graph.py              # Agent graph construction and validation
│   ├── portfolio.py          # Portfolio construction
│   ├── run_store.py          # Run-history recording
│   └── streaming.py          # Shared SSE lifecycle
├── __init__.py               # Package marker
└── main.py                   # FastAPI application entry point
```

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it solely for learning purposes.