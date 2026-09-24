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
# From the repository root, not from app/backend: main.py imports
# app.backend.routes, which only resolves with the root on sys.path.
poetry run uvicorn app.backend.main:app --reload
```

This will start the FastAPI server with hot-reloading enabled.

The API will be available at:
- API Endpoint: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Welcome message |
| `GET` | `/ping` | Server-Sent Event keepalive, for testing connectivity |
| `GET` | `/agents` | The analyst catalog, from `src/utils/analysts.py` |
| `GET` | `/models` | The model catalog, cloud and Ollama |
| `POST` | `/hedge-fund/run` | Run the hedge fund, streaming progress as SSE |
| `POST` | `/backtest/run` | Run a backtest, streaming one event per simulated day |

Both `POST` endpoints stream `start`, `progress`, `complete` and `error`
events; `/backtest/run` also streams `backtest_day`. Every event carries the
request's `run_id`. An empty or unknown `selected_agents` list returns `400`.

## Project Structure

```
app/backend/
├── models/                   # Domain models
│   ├── __init__.py
│   ├── events.py             # Server-Sent Event payloads
│   └── schemas.py            # Pydantic request and response schemas
├── routes/                   # API routes
│   ├── __init__.py           # Router registry
│   ├── backtest.py           # Backtest endpoint
│   ├── catalog.py            # Agent and model catalogs
│   ├── hedge_fund.py         # Hedge fund endpoints
│   └── health.py             # Health check endpoints
├── services/                 # Business logic
│   ├── graph.py              # Agent graph assembly and execution
│   └── portfolio.py          # Portfolio construction
├── __init__.py               # Package initialization
└── main.py                   # FastAPI application entry point
```

`routes/` is the API layer; there is no separate `api/` package.

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it solely for learning purposes.