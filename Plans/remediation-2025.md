# Remediation packages F1–F12

Derived from an audit of the repository at `4212e31` and the root-cause
analysis that followed it. Thirty-two findings collapsed to nine root causes;
these twelve packages are the fixes, ordered by dependency rather than by
severity.

Status key: **Done** · **Partial** · **Deferred**.

---

## F1 — Green the build and add a gate

**Problem.** `.github/` held only `ISSUE_TEMPLATE/`, so `tsc`, `vite build`,
`eslint`, `black`, `flake8` and `pytest` had never run automatically.
Development happened only on case-insensitive macOS, so `App.tsx` importing
`./components/flow` while the tracked file is `Flow.tsx` resolved locally and
failed everywhere else. Alongside it: 132 lint errors, six type errors in the
vendored shadcn sidebar, an unvalidated `--tickers`, and zero tests.

**Done.**
- Import specifiers in `App.tsx` corrected; `vite build` and `tsc --noEmit` pass.
- The sidebar's `asChild` components declare props with `ComponentPropsWithoutRef`, which is the correct shape for a `forwardRef` component.
- `npm run lint` passes at `--max-warnings 0`.
- `.github/workflows/ci.yml` runs on `ubuntu-latest`: black, flake8, mypy, pytest, plus frontend lint and build.
- `tests/` seeded with the margin invariant, cache coverage, JSON extraction, run scoping and the HTTP surface.
- `--tickers` is required on the backtester.

---

## F2 — Restore onboarding and align the docs

**Problem.** `4212e31` deleted `.env.example`. `run.sh:221-231` and
`run.bat:249-258` bootstrap `.env` from it and `exit 1` when it is absent, so
every documented run command died on a clean clone. `OPENAI_API_BASE` lost its
only documentation surface.

**Done.** Template restored with the three undocumented variables added;
`app/frontend/.env.example` created; the backend start command corrected to
`uvicorn app.backend.main:app` from the repository root in both READMEs; the
"and backtester" claim made true by F9.

---

## F3 — CLI parity and dead code

**Problem.** `--analysts` and `--analysts-all` existed only on the backtester;
`main.py` ran all 14 analysts with no opt-out. Neither run script forwarded
them, and nothing let the container path skip the model prompt.

**Done.** Both flags on both entry points, sharing one selection helper so
they cannot drift apart again; the interactive picker restored as the no-flag
default; `--model-name` and `--model-provider` added; `run.sh` and `run.bat`
forward all four.

**Correction to the audit.** Finding A18 reported `src/utils/docker.py` as
dead code with zero importers, and F3 proposed deleting it. It is not dead:
`src/utils/ollama.py` imports it as `from . import docker` and delegates when
`OLLAMA_BASE_URL` points at a container. The differing signature is
deliberate — the daemon is remote and cannot be installed from the process.
Kept and documented.

---

## F4 — One portfolio model, one valuation

**Problem.** The identical portfolio dict was built in three places and valued
in two, and both valuation sites omitted the margin posted against shorts. With
`margin_requirement > 0` and an open short, net liquidation value was
understated by exactly `margin_used`, corrupting total return, Sharpe, Sortino,
max drawdown, win rate, and the position limit gating every later trade.

**Done.** `src/data/portfolio.py` owns the shape and
`cash + margin_used + Σ long×price − Σ short×price`. All three constructors
and both valuation sites point at it. The backtester refreshes metrics before
the summary row reads them. The position limit is configurable.

---

## F5 — Cache coverage

**Problem.** Readers short-circuited whenever *any* cached row fell inside the
requested window, so a cache holding five January days answered a six-month
query with five rows — silently, with agents reasoning over the truncation at
full confidence.

**Done.** The cache records fetched date ranges and serves only fully covered
requests; `get_prices` fetches the uncovered gaps and merges. Metrics and line
items are keyed by period and requested field set, with a short upstream
history remembered so it is not refetched every call. Line items are cached,
which the orphaned `# Cache the results` comment had promised.

**Deferred.** Disk persistence and TTL. The cache is still per-process.

---

## F6 — Run-scoped state

**Problem.** `progress` and `_cache` were one-run-per-process CLI singletons
that the API imported verbatim. Two concurrent requests pushed into one
handler list, so each browser animated the other's agents, and `agent_status`
accumulated forever. `register_handler` was annotated for three arguments and
called with four.

**Done.** Handlers register per `run_id`, with a contextvar scope so agents
keep calling `update_status` unaware of runs. `run_id` on every request and
every event. The annotation matches the call. `run_hedge_fund` takes its
compiled graph as a parameter instead of reaching for a module global that
only existed under `__main__`. `merge_dicts` deep-merges.

**Deferred.** A per-run `Cache`. Threading one through would touch every call
site in all 16 agent modules; the shared cache is correct now that coverage is
tracked, but it is still cross-tenant.

---

## F7 — Serve the catalogs

**Problem.** `ANALYST_CONFIG` calls itself the single source of truth, but the
frontend re-declared the catalogs by hand and the copy had already gone lossy:
it omitted Ollama, making the local-LLM path unreachable from the web app. The
`has_json_mode` allow-list still tested only for `llama3`, while six newer
Ollama models had shipped.

**Done.** `GET /agents` and `GET /models`; the hand-copied TypeScript deleted;
`supports_json_mode` declared in the catalog JSON; `extract_json_from_response`
widened to bare JSON, plain fences and JSON in prose; `default_factory`
consulted on the parse-failure path; `get_model` raises on an unknown provider.

---

## F8 — Close the web contract

**Problem.** A graph failure re-raised inside the generator after the `200` and
`start` event were flushed, so clients saw the stream stop with no reason.
Status was written to a node id that does not exist; the two always-on stages
could never render; only one-hop agent selection worked while the real path
resolver sat unused; duplicate agents collided on `id: agent.key`.

**Done.** Errors emitted as `ErrorEvent` and surfaced in the UI; one shared
node-id module; risk manager and portfolio manager placeable on the canvas;
`getNodesInCompletePaths` wired into the run; unique node ids; server-side
validation returning `400`.

---

## F9 — Backtest over HTTP, then charts

**Problem.** Both app READMEs promised "the hedge fund trading system and
backtester", but 776 lines of metrics logic were CLI-only.

**Done.** `POST /backtest/run` streams one event per simulated day and returns
metrics plus equity curve. The canvas gains an Analyze/Backtest toggle, an
equity curve, a drawdown chart and a metrics panel, and renders the risk
manager's per-ticker exposure that nothing had displayed.

---

## F10 — Headless rendering

**Problem.** `plt.show()` blocked on a GUI loop and wrote no file, so Docker
and CI produced no chart. `save_graph_as_png` posted to mermaid.ink, so
`--show-agent-graph` failed offline.

**Done.** matplotlib selects `Agg` when `DISPLAY` and `MPLBACKEND` are unset;
`--chart-output` saves the equity curve; `--graph-output` names the graph PNG;
the graph renders locally with the hosted API as fallback.

---

## F11 — Container the web app

**Problem.** `run.sh` referenced `docker-compose.nvidia.yml`, never committed,
so every compose command on an NVIDIA host failed. Compose had no service for
FastAPI or Vite. Each service bind-mounted `./.env`, which Docker silently
creates as a *directory* when the file is absent. The Dockerfile installed the
root package before copying the source it declares.

**Done.** The NVIDIA overlay committed and its reference guarded; `backend` and
`frontend` services added; bind mounts replaced with `env_file`; the Dockerfile
installs dependencies with `--no-root` and the project after the copy.

**Not verified.** No Docker daemon was available, so the image build and the
compose topology are reasoned from the files, not observed.

---

## F12 — Enforce conventions, then the backlog

**Problem.** `black`, `isort` and `flake8` were declared and never invoked, and
`black`'s line-length of 420 suppressed reformatting. `dict[str, any]` used the
builtin. Metadata was still `Your Name` and `vite-react-flow-template`.

**Done.** black at 200 applied and enforced in CI; flake8 configured; mypy
added over `src/data` and the two utils modules the tree depends on; the
annotation defects fixed; metadata corrected; duplicate lockfiles and a stray
root `package.json` removed; `ARCHITECTURE.md` written; this directory created.

**Deferred, with reasons.**

| Item | Why |
|---|---|
| Persistence layer (`sqlalchemy` + `alembic` are declared) | Nothing in the product yet needs durable state; adding schema and migrations before there is a reader would be speculative. The dependencies stay declared for the eventual run history. |
| Auth and rate limiting | The API binds to localhost for a single-user desktop tool. Adding auth is a product decision about deployment shape, not a defect fix. |
| `api/` package | `routes/` is the API layer. The README no longer implies a second one. |
| Sidebar placeholders: Data Store, Vector Store, Code Processor, Function, Chat Input, File Input | The engine has no notion of any of them. Shipping nodes that cannot run would be worse than their absence. They remain commented out as intent markers. |
| Per-run `Cache` | See F6. |
