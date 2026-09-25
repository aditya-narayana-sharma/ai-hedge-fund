# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund.  The goal of this project is to explore the use of AI to make trading decisions.  This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several agents working together:

1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
7. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
8. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research 
9. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
10. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
11. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
12. Sentiment Agent - Analyzes market sentiment and generates trading signals
13. Fundamentals Agent - Analyzes fundamental data and generates trading signals
14. Technicals Agent - Analyzes technical indicators and generates trading signals
15. Risk Manager - Calculates risk metrics and sets position limits
16. Portfolio Manager - Makes final trading decisions and generates orders
    
<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />


**Note**: the system simulates trading decisions, it does not actually trade.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [Setup](#setup)
  - [Using Poetry](#using-poetry)
  - [Using Docker](#using-docker)
- [Usage](#usage)
  - [Running the Hedge Fund](#running-the-hedge-fund)
  - [Running the Backtester](#running-the-backtester)
  - [Running the Web Application](#running-the-web-application)
  - [Selecting Analysts](#selecting-analysts)
- [Configuration](#configuration)
- [Development](#development)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [Feature Requests](#feature-requests)
- [License](#license)

## Setup

### Using Poetry

Clone the repository:
```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

3. Set up your environment variables:
```bash
# Create .env file for your API keys
cp .env.example .env
```

4. Set your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
# Get your OpenAI API key from https://platform.openai.com/
OPENAI_API_KEY=your-openai-api-key

# For running LLMs hosted by groq (deepseek, llama3, etc.)
# Get your Groq API key from https://groq.com/
GROQ_API_KEY=your-groq-api-key

# For getting financial data to power the hedge fund
# Get your Financial Datasets API key from https://financialdatasets.ai/
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

### Using Docker

1. Make sure you have Docker installed on your system. If not, you can download it from [Docker's official website](https://www.docker.com/get-started).

2. Clone the repository:
```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

3. Set up your environment variables:
```bash
# Create .env file for your API keys
cp .env.example .env
```

4. Edit the .env file to add your API keys as described above.

5. Build the Docker image:
```bash
# On Linux/Mac:
./run.sh build

# On Windows:
run.bat build
```

**Important**: You must set `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY` for the hedge fund to work.  If you want to use LLMs from all providers, you will need to set all API keys.

Financial data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key.

For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## Usage

### Running the Hedge Fund

#### With Poetry
```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

#### With Docker
```bash
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA main

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA main
```

**Example Output:**
<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

You can also specify a `--ollama` flag to run the AI hedge fund using local LLMs.

```bash
# With Poetry:
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# With Docker (on Linux/Mac):
./run.sh --ticker AAPL,MSFT,NVDA --ollama main

# With Docker (on Windows):
run.bat --ticker AAPL,MSFT,NVDA --ollama main
```

You can also specify a `--show-reasoning` flag to print the reasoning of each agent to the console.

```bash
# With Poetry:
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --show-reasoning

# With Docker (on Linux/Mac):
./run.sh --ticker AAPL,MSFT,NVDA --show-reasoning main

# With Docker (on Windows):
run.bat --ticker AAPL,MSFT,NVDA --show-reasoning main
```

You can optionally specify the start and end dates to make decisions for a specific time period.

```bash
# With Poetry:
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 

# With Docker (on Linux/Mac):
./run.sh --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 main

# With Docker (on Windows):
run.bat --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 main
```

### Running the Backtester

#### With Poetry
```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

#### With Docker
```bash
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA backtest

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA backtest
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


You can optionally specify the start and end dates to backtest over a specific time period.

```bash
# With Poetry:
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01

# With Docker (on Linux/Mac):
./run.sh --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 backtest

# With Docker (on Windows):
run.bat --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 backtest
```

You can also specify a `--ollama` flag to run the backtester using local LLMs.
```bash
# With Poetry:
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --ollama

# With Docker (on Linux/Mac):
./run.sh --ticker AAPL,MSFT,NVDA --ollama backtest

# With Docker (on Windows):
run.bat --ticker AAPL,MSFT,NVDA --ollama backtest
```

The equity-curve chart opens in a window when there is a display, and is
written to a file when there is not (Docker, CI, a plain SSH session). Name the
file explicitly with `--chart-output path/to/chart.png`.

### Running the Web Application

A React Flow canvas for composing the agent graph and watching each node run,
backed by a FastAPI server.

```bash
# With Docker (backend + canvas together):
./run.sh web          # Linux/Mac
run.bat web           # Windows

# Or run the two halves directly, from the REPOSITORY ROOT:
poetry run uvicorn app.backend.main:app --reload
cd app/frontend && npm install && npm run dev
```

- Canvas: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

The backend exposes `GET /agents`, `GET /models`, `POST /hedge-fund/run` and
`POST /backtest`. The last two stream Server-Sent Events, so the canvas lights
up agent by agent as the run proceeds; the backtest returns an equity curve,
drawdown and exposure charts.

### Selecting Analysts

Both entry points take the same flags. With neither, an interactive picker
appears:

```bash
# Every analyst, non-interactive (what Docker uses by default)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --analysts-all

# A specific subset
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --analysts warren_buffett,michael_burry

# Same flags on the backtester and through the run scripts
./run.sh --ticker AAPL,MSFT,NVDA --analysts warren_buffett main
```

## Configuration

Every variable is documented in [`.env.example`](.env.example). At least one
LLM provider key is required.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY` | LLM providers. Set at least one. |
| `FINANCIAL_DATASETS_API_KEY` | Market data. Optional — AAPL, GOOGL, MSFT, NVDA and TSLA are free without it. |
| `OPENAI_API_BASE` | Point the OpenAI client at a compatible gateway (Azure, LiteLLM, OpenRouter, vLLM). |
| `OLLAMA_HOST`, `OLLAMA_BASE_URL` | Reach an Ollama server that is not on localhost. `OLLAMA_BASE_URL` also selects the remote code path. |
| `VITE_API_URL` | Backend URL the canvas calls. Defaults to `http://localhost:8000`. See [`app/frontend/.env.example`](app/frontend/.env.example). |
| `AI_HEDGE_FUND_CORS_ORIGINS` | Comma-separated browser origins the API accepts. Defaults to the two Vite dev servers. |
| `AI_HEDGE_FUND_API_KEY` | When set, the run endpoints require a matching `X-API-Key` header. Unset means open. |
| `AI_HEDGE_FUND_RATE_LIMIT`, `AI_HEDGE_FUND_RATE_LIMIT_WINDOW` | Requests allowed per client per window. Unset or `0` disables rate limiting. |
| `AI_HEDGE_FUND_DATABASE_URL` | When set, run history is persisted. Unset means no database is opened. |
| `AI_HEDGE_FUND_CACHE_TTL`, `AI_HEDGE_FUND_CACHE_DIR` | Optional expiry and on-disk persistence for the market-data cache. |

Runtime flags shared by both CLI entry points: `--tickers`, `--start-date`,
`--end-date`, `--initial-cash` / `--initial-capital`, `--margin-requirement`,
`--position-limit`, `--analysts` / `--analysts-all`, `--show-reasoning`,
`--ollama`.

## Development

```bash
poetry install

poetry run pytest                     # tests
poetry run flake8 src app tests       # lint
poetry run black --check src app tests
poetry run isort --check-only src app tests
poetry run mypy                       # types

cd app/frontend
npm ci && npm run lint && npm run build
```

CI runs exactly this on `ubuntu-latest` for every pull request
(`.github/workflows/ci.yml`). The Linux runner is deliberate: it is
case-sensitive, which is what stops filename-casing import bugs from reaching
`main`.

## Project Structure 
```
ai-hedge-fund/
├── src/
│   ├── agents/                   # Agent definitions and workflow
│   │   ├── bill_ackman.py        # Bill Ackman agent
│   │   ├── fundamentals.py       # Fundamental analysis agent
│   │   ├── portfolio_manager.py  # Portfolio management agent
│   │   ├── risk_manager.py       # Risk management agent
│   │   ├── sentiment.py          # Sentiment analysis agent
│   │   ├── technicals.py         # Technical analysis agent
│   │   ├── valuation.py          # Valuation analysis agent
│   │   ├── ...                   # Other agents
│   │   ├── warren_buffett.py     # Warren Buffett agent
│   │   ├── aswath_damodaran.py   # Aswath Damodaran agent
│   │   ├── ...                   # Other agents
│   │   ├── ...                   # Other agents
│   ├── data/                     # Cache, response models, portfolio model
│   │   ├── cache.py              # Coverage-tracking API cache
│   │   ├── portfolio.py          # Portfolio shape + net liquidation value
│   ├── graph/                    # LangGraph state and reducers
│   ├── llm/                      # Provider clients and model catalogs
│   ├── tools/                    # Agent tools
│   │   ├── api.py                # financialdatasets.ai client
│   ├── utils/                    # Progress, run context, charts, parsing
│   ├── backtester.py             # Backtesting tools
│   ├── main.py                   # Main entry point
├── app/
│   ├── backend/                  # FastAPI server
│   │   ├── api/                  # Router composition, auth, rate limiting
│   │   ├── database/             # Optional run-history persistence
│   │   ├── models/               # Request, response and SSE event schemas
│   │   ├── routes/               # Endpoint implementations
│   │   ├── services/             # Graph construction, streaming, backtest
│   ├── frontend/                 # React Flow canvas
├── migrations/                   # Alembic migrations
├── tests/                        # pytest suite
├── Plans/                        # Requirement documents for planned work
├── ARCHITECTURE.md               # Data flow across all three tiers
├── pyproject.toml
├── ...
```

## Architecture

[`ARCHITECTURE.md`](ARCHITECTURE.md) covers the data flow across all three
tiers — CLI and HTTP entry points, the LangGraph fan-out, caching, run
isolation, and the SSE contract between the backend and the canvas.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
