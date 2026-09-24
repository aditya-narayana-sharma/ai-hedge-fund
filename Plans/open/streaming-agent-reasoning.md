# Stream agent reasoning to the canvas

## Problem

`--show-reasoning` exists on the CLI (`src/main.py`) and flows through
`AgentState["metadata"]["show_reasoning"]` to `show_agent_reasoning()` in
`src/graph/state.py`, which prints to stdout.

The web path hard-codes `"show_reasoning": False`
(`app/backend/services/graph.py`), so the canvas can only display the summary
reasoning that arrives in the terminal `complete` event. Watching *why* an
agent reached its signal — the thing the per-agent dialog is shaped for — is
CLI-only.

## Proposal

1. Add `show_reasoning: bool = False` to `RunRequestBase`
   (`app/backend/models/schemas.py`) and thread it into the graph metadata.
2. Add a `reasoning` SSE event carrying `run_id`, `agent`, `ticker` and the
   structured reasoning payload, emitted from `show_agent_reasoning` through
   the active `RunContext` rather than printed.
3. Render it in `agent-output-dialog.tsx` beside the existing message log.

## Scope

Changes: `app/backend/models/{schemas,events}.py`,
`app/backend/services/{graph,streaming}.py`, `src/graph/state.py`,
`app/frontend/src/services/api.ts`,
`app/frontend/src/nodes/components/agent-output-dialog.tsx`.

Out of scope: token-level streaming from the providers. This streams completed
per-agent reasoning, not partial generations.

## Verification

A test asserting that a run with `show_reasoning: true` emits at least one
`reasoning` event and that one with it `false` emits none.
