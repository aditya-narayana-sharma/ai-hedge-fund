# Architecture

How a ticker becomes a simulated trading decision, and which module owns each
step. The README's "Project Structure" tree is a file listing and omits `app/`
entirely; this document covers the data flow across all three tiers.

> This is an educational simulator. It never places an order.

---

## The three tiers

| Tier | Path | Role |
|---|---|---|
| **Engine** | `src/` | A LangGraph orchestrator that fans a ticker list out to 14 analyst agents, funnels their signals through a risk manager, and has a portfolio manager emit orders. |
| **API** | `app/backend/` | A FastAPI wrapper that streams the engine's progress and results over Server-Sent Events. |
| **Canvas** | `app/frontend/` | A React Flow node editor where the agent graph is composed by wiring nodes, then watched live. |

## Entry points

There are three, and they all converge on the same graph:

| Entry point | Module | Shape |
|---|---|---|
| CLI, one pass | `src/main.py` | Build the graph, invoke once, print tables. |
| CLI, backtest | `src/backtester.py` | One full invoke per business day across a date range. |
| HTTP | `app/backend/routes/` | `POST /hedge-fund/run` and `POST /backtest`, both streaming SSE. |

```
src/main.py ─┐
             ├─> create_workflow / create_graph ─> LangGraph ─> decisions
backtester ──┤                                       │
             │                                       ├─> src/tools/api.py ─> cache ─> financialdatasets.ai
FastAPI ─────┘                                       └─> src/utils/llm.py ─> src/llm/models.py ─> provider
```

## The graph

`start_node` fans out to every selected analyst in parallel, all of them
converge on the risk manager, and the portfolio manager turns the collected
signals into orders.

```
                 ┌─ 10 persona agents (Buffett, Graham, Ackman, Wood, Munger,
                 │   Burry, Lynch, Fisher, Druckenmiller, Damodaran)
start_node ──────┤                                                   ─┬─> risk_management_agent ──> portfolio_manager ──> END
                 └─ 4 quant agents (technicals, fundamentals,         │
                     sentiment, valuation)                           ─┘
```

Division of labour:

| Stage | LLM calls | Reads |
|---|---|---|
| Persona agents | 2 each | metrics, line items, market cap; several also read news and insider trades |
| Quant agents | **0** | metrics / prices / insider trades + news — pure functions of cached data |
| Risk manager | **0** | prices only |
| Portfolio manager | 2 | nothing; consumes `analyst_signals` |

The quant agents being LLM-free is load-bearing: their output is a pure
function of what the cache returned, so a truncated data window changes their
signals silently and with full confidence. That is why `src/data/cache.py`
tracks coverage (see below).

## State

`src/graph/state.py` defines `AgentState`:

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data:     Annotated[dict[str, Any], merge_dicts]
    metadata: Annotated[dict[str, Any], merge_dicts]
```

`data` carries `tickers`, `portfolio`, `start_date`, `end_date` and
`analyst_signals`. `metadata` carries `show_reasoning`, `model_name`,
`model_provider` and `position_limit`.

`merge_dicts` is a **deep** merge. A shallow one worked only because every
analyst mutated a single shared `analyst_signals` dict in place; the moment two
parallel branches return disjoint partials — which checkpointing, `Send`-based
fan-out or thread isolation would cause — a shallow merge drops one branch
wholesale.

## Portfolio and valuation

`src/data/portfolio.py` is the single definition of the portfolio shape and of
net liquidation value:

```
NLV = cash + margin_used + Σ(long × price) − Σ(short × price)
```

`margin_used` is added back because opening a short *reduces* cash by the
posted margin. That cash is collateral, not an expense. Every construction site
(`src/main.py`, `src/backtester.py`, `app/backend/services/portfolio.py`) and
both valuation sites (`src/backtester.py`, `src/agents/risk_manager.py`) route
through this module, because when they did not, two of them omitted the margin
term and understated NLV — which corrupted total return, Sharpe, Sortino,
drawdown, win rate, and the position limit that gates every subsequent trade.

## Data and caching

`src/tools/api.py` is the only client of financialdatasets.ai. Every reader
follows the same shape:

1. Ask the cache which sub-ranges of `[start_date, end_date]` are **not** yet fetched.
2. Fetch only those, and record the range as covered — even when the API returned nothing, so holidays and pre-IPO windows are not re-fetched forever.
3. Serve the whole window from the cache.

`src/data/cache.py` stores rows *and* the date ranges they came from. Without
that coverage record, any single overlapping row short-circuited the fetch, so
a cache holding five January days satisfied a six-month query with five rows.

The cache is per run (see below), with optional TTL
(`AI_HEDGE_FUND_CACHE_TTL`) and optional disk persistence
(`AI_HEDGE_FUND_CACHE_DIR`).

## LLM access

`src/llm/models.py` loads two catalogs — `api_models.json` (cloud) and
`ollama_models.json` (local) — each entry declaring `supports_json_mode`
alongside its name, so a model's capability travels with it.

`src/utils/llm.py` calls the model with up to three retries. Models with JSON
mode use LangChain structured output; the rest are parsed by
`src/utils/json_parsing.py`, which accepts bare JSON, ```` ```json ```` fences,
plain fences, and an object embedded in prose. If every attempt fails, the
caller's `default_factory` is used — on both the exception path and the
parse-failure path.

## Run isolation

The CLI runs one simulation per process; the web backend does not. A run owns
its own cache, progress handlers and agent-status map, published through a
`ContextVar` in `src/utils/run_context.py`:

```
POST /hedge-fund/run
  └─ new_run_context(run_id)         # own Cache, own handler list
     └─ asyncio.to_thread(...)       # copies the context into the worker
        └─ LangGraph thread pool     # LangChain's executor copies it again
           └─ agents resolve_cache() / progress.update_status()
```

Outside a run scope — the CLI — everything falls back to the process-wide
instances and the live `rich` status table.

## The SSE contract

Both run endpoints stream the same envelope via
`app/backend/services/streaming.py`:

| Event | Payload |
|---|---|
| `start` | `run_id` |
| `progress` | `run_id`, `agent`, `ticker`, `status`, `timestamp` |
| `complete` | `run_id`, `data` (decisions + analyst signals, or backtest metrics) |
| `error` | `run_id`, `message` |

Every event carries `run_id`, and the response echoes it in the `X-Run-Id`
header. `error` is emitted whenever the work raises, including after the `200`
and the `start` event have already been flushed.

The frontend cannot use `EventSource` because the request carries a JSON body,
so `src/services/api.ts` reads the body stream and parses frames itself.

### Agent name to node mapping

`app/frontend/src/data/node-mappings.ts` is the only place that knows how
backend agent names relate to canvas nodes. Analysts arrive as `<key>_agent`;
`risk_management_agent`, `portfolio_manager`, `system` and `backtester` arrive
verbatim and are listed explicitly, because naively stripping `_agent` turns
`risk_management_agent` into a key that matches nothing.

Node status is keyed by **agent identity**, not node id, so node ids can be
unique per instance and the same agent can appear on the canvas twice.

## HTTP surface

| Method | Path | Notes |
|---|---|---|
| `GET` | `/` | Welcome |
| `GET` | `/ping` | SSE keepalive demo |
| `GET` | `/agents` | Analyst catalog, from `ANALYST_CONFIG` |
| `GET` | `/models` | Model catalog, cloud and Ollama |
| `POST` | `/hedge-fund/run` | One pass, SSE |
| `POST` | `/backtest` | Day-by-day simulation, SSE |

`/agents` and `/models` exist so the canvas stops re-declaring both catalogs by
hand. Composition, authentication and rate limiting live in
`app/backend/api/`; the endpoint modules live in `app/backend/routes/`.

## Persistence

Optional, and off unless `AI_HEDGE_FUND_DATABASE_URL` is set. When it is,
`app/backend/database/` records one row per run (parameters, status, result or
error) and Alembic owns the schema: `alembic upgrade head`.

## Rendering without a display

`src/utils/charts.py` selects the non-interactive `Agg` matplotlib backend when
no display is available, and always writes a file in that case, so a container
or CI job produces an artifact instead of nothing. `src/utils/visualize.py`
renders the agent graph locally before falling back to mermaid.ink, and writes
Mermaid source if neither renderer is available.

## Quality gates

`.github/workflows/ci.yml` runs on `ubuntu-latest`, which is case-sensitive by
construction — the property that keeps the `App.tsx` import-casing regression
from returning.

- Python: `flake8`, `black --check`, `isort --check-only`, `mypy`, `pytest`
- Frontend: `npm ci`, `npm run lint`, `npm run build`
