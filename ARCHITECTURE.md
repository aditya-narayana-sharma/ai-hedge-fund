# Architecture

How a request travels from an entry point, through the agent graph, to a set
of simulated trading decisions. This is an educational simulator: nothing here
places an order.

## The three layers

| Layer | Path | Role |
|---|---|---|
| Engine | `src/` | A LangGraph orchestrator that fans a ticker list out to 14 analysts, funnels their signals through a risk manager, and has a portfolio manager emit orders. |
| API | `app/backend/` | A FastAPI wrapper exposing the engine over Server-Sent Events. |
| Canvas | `app/frontend/` | A React Flow node editor where the agent graph is composed by wiring nodes, then watched live. |

## Entry points

Three, all converging on the same graph:

- `src/main.py` — the CLI. One pass as of a given date.
- `src/backtester.py` — wraps the CLI's `run_hedge_fund` in a loop, one full pass per business day, after a one-year data prefetch.
- `app/backend/routes/` — `POST /hedge-fund/run` for a single pass, `POST /backtest/run` for a range. Both stream progress.

## The graph

```
                    start_node
                        │
        ┌───────────────┼───────────────┐
        │                               │
  10 persona agents               4 quant agents
  Buffett · Graham · Ackman       technicals · fundamentals
  Wood · Munger · Burry           sentiment · valuation
  Lynch · Fisher                  (no LLM call: pure functions
  Druckenmiller · Damodaran        of cached market data)
        │                               │
        └───────────────┬───────────────┘
                        │
              risk_management_agent      position limits from
                        │                net liquidation value
                portfolio_manager        buy / sell / short / cover
                        │
                       END
```

The risk and portfolio stages are appended to every graph regardless of what
the caller selected (`app/backend/services/graph.py`, `src/main.py`). The
canvas shows them as nodes so the two always-on stages are visible.

State is an `AgentState` TypedDict (`src/graph/state.py`) with three keys:
`messages` (appended), and `data` and `metadata` (deep-merged). The deep merge
matters: a shallow one would let two parallel branches overwrite each other's
`analyst_signals` wholesale.

## Data flow

1. **Selection.** `selected_agents` is validated against `ANALYST_CONFIG`. An empty or unknown list is a `400`, not an empty-signals `200`.
2. **Fetch.** `src/tools/api.py` reads through `src/data/cache.py` to financialdatasets.ai. The cache records *which date ranges have been fetched*, not just which rows it holds, and only serves a fully covered request — otherwise it fetches the gaps and merges.
3. **Reason.** Each analyst writes `state["data"]["analyst_signals"][<agent>]`. Persona agents make two LLM calls each; the four quant agents make none.
4. **Size and decide.** The risk manager values the portfolio at `cash + margin_used + Σ long×price − Σ short×price` (`src/data/portfolio.py`) and caps each ticker at a configurable share of it. The portfolio manager turns signals plus limits into orders.
5. **Report.** The CLI prints tables; the API emits a `complete` event carrying decisions and analyst signals.

## Progress and run scoping

Agents report progress through the module-level `progress` tracker
(`src/utils/progress.py`). Handlers are registered per `run_id`, and a
contextvar run scope tags updates that agents emit without knowing about runs,
so two concurrent HTTP requests do not stream into each other. The CLI
registers no `run_id` and sees everything.

The executor thread that runs the graph does not inherit the request's
context, so `run_graph` enters the run scope itself.

## The SSE contract

Server-Sent Events over `POST`, which rules out `EventSource`: the request
carries a JSON body, so the frontend reads `response.body` and splits on blank
lines.

| Event | Payload |
|---|---|
| `start` | `run_id` |
| `progress` | `agent`, `ticker`, `status`, `timestamp` |
| `backtest_day` | `date`, `portfolio_value`, `return_pct` |
| `complete` | `data` — decisions and analyst signals, or the backtest report |
| `error` | `message` |

A graph failure is caught inside the generator and emitted as `error`. The
`200` and the `start` event are already on the wire by then, so an exception
that escapes would only look like the stream stopping.

## Catalogs

`src/utils/analysts.py` holds `ANALYST_CONFIG` and `src/llm/*.json` hold the
model catalogs. The frontend cannot import Python, so it fetches `GET /agents`
and `GET /models` at startup rather than re-declaring them in TypeScript.
`src/llm/api_models.json` and `ollama_models.json` each carry a
`supports_json_mode` flag, so a model's capability travels with its catalog
entry instead of being inferred from its name.

## Canvas to backend

`app/frontend/src/data/node-ids.ts` is the single place that knows how backend
agent names line up with canvas nodes. Agent nodes carry their catalog key in
`data.agentKey` and have unique ids, so the same agent can be placed twice;
node status is keyed by the name the backend reports under
(`<key>_agent`, or `risk_management_agent` / `portfolio_manager`).

A run collects the agents on a complete path from the input node to the output
node (`getNodesInCompletePaths`), so chained topologies work and a dangling
agent does not join the run.

## Configuration

Environment variables are documented in `.env.example` (repository root) and
`app/frontend/.env.example`. One LLM provider key is required; the data API key
is optional, since AAPL, GOOGL, MSFT, NVDA and TSLA are free without it.

## Quality gates

`.github/workflows/ci.yml` runs on `ubuntu-latest` — case-sensitive by
construction, which is what catches filename-casing bugs that resolve on
macOS. It runs `black --check`, `flake8`, `mypy` and `pytest` for Python, and
`npm run lint` plus `npm run build` for the frontend.
