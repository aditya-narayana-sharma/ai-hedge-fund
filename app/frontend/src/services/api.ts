import { NodeStatus, OutputNodeData, useNodeContext } from '@/contexts/node-context';
import { OUTPUT_KEY, statusKeyForAgent } from '@/data/node-mappings';
import { BacktestResult, ModelProvider } from '@/services/types';

import { API_BASE_URL } from './config';

interface RunRequest {
  tickers: string[];
  selected_agents: string[];
  end_date?: string;
  start_date?: string;
  model_name?: string;
  model_provider?: ModelProvider;
  initial_cash?: number;
  margin_requirement?: number;
  position_limit?: number;
  /** Replaces the default opening instruction sent to the agents. */
  prompt?: string;
}

/** Map a free-text progress status onto the canvas vocabulary. */
function progressNodeStatus(status: string): NodeStatus {
  if (status === 'Done') return 'COMPLETE';
  if (status.startsWith('Failed:') || status.startsWith('Warning:') || status.startsWith('Error')) {
    return 'ERROR';
  }
  return 'IN_PROGRESS';
}

/** A cancelled fetch rejects with an AbortError; that is expected, not a failure. */
function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

interface ParsedEvent {
  type: string;
  data: Record<string, unknown>;
}

/**
 * Consume an SSE stream delivered over POST.
 *
 * EventSource cannot be used because the request carries a JSON body, so the
 * frame parsing is hand-rolled: read the body, split on the blank line that
 * terminates each frame, and pull `event:` and `data:` out of what is left.
 */
async function readEventStream(response: Response, onEvent: (event: ParsedEvent) => void): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('Failed to get response reader');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split('\n\n');
    buffer = frames.pop() || ''; // keep the trailing partial frame

    for (const frame of frames) {
      if (!frame.trim()) continue;

      const typeMatch = frame.match(/^event: (.+)$/m);
      const dataMatch = frame.match(/^data: (.+)$/m);
      if (!typeMatch || !dataMatch) continue;

      try {
        onEvent({ type: typeMatch[1], data: JSON.parse(dataMatch[1]) });
      } catch (err) {
        console.error('Error parsing SSE event:', err, 'Raw event:', frame);
      }
    }
  }
}

async function postJson(path: string, body: unknown, signal: AbortSignal): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    // 400 and 401 carry a FastAPI `detail` worth showing the user.
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // Body was not JSON; the status line is all we have.
    }
    throw new Error(detail);
  }

  return response;
}

export const api = {
  /**
   * Run a hedge fund simulation, streaming node status into the node context.
   * @returns a function that aborts the stream.
   */
  runHedgeFund: (params: RunRequest, nodeContext: ReturnType<typeof useNodeContext>): (() => void) => {
    const controller = new AbortController();

    const fail = (message: string) => {
      console.error('Hedge fund run failed:', message);
      nodeContext.setRunError(message);
      nodeContext.settleRun(params.selected_agents || [], 'ERROR');
    };

    (async () => {
      nodeContext.setIsRunning(true);
      try {
        const response = await postJson('/hedge-fund/run', params, controller.signal);

        await readEventStream(response, ({ type, data }) => {
          switch (type) {
            case 'start':
              nodeContext.resetAllNodes();
              nodeContext.setIsRunning(true);
              break;

            case 'progress': {
              const agent = data.agent as string | undefined;
              if (!agent) break;
              const status = String(data.status ?? '');
              nodeContext.updateAgentNode(statusKeyForAgent(agent), {
                status: progressNodeStatus(status),
                ticker: (data.ticker as string | null) ?? null,
                message: status,
                timestamp: data.timestamp as string | undefined,
              });
              break;
            }

            case 'complete':
              if (data.data) {
                nodeContext.setOutputNodeData(data.data as OutputNodeData);
              }
              nodeContext.settleRun(params.selected_agents || [], 'COMPLETE');
              nodeContext.updateAgentNode(OUTPUT_KEY, {
                status: 'COMPLETE',
                message: 'Analysis complete',
              });
              break;

            case 'error':
              // The backend now reports why a run died instead of just closing
              // the stream, so the message can reach the user.
              fail((data.message as string) || 'The run failed without a message.');
              break;

            default:
              console.warn('Unknown event type:', type);
          }
        });
      } finally {
        nodeContext.setIsRunning(false);
      }
    })().catch((error: unknown) => {
      if (isAbortError(error)) return;
      fail(describe(error));
    });

    return () => controller.abort();
  },

  /**
   * Run a backtest, streaming progress into the node context and resolving
   * with the completed result.
   */
  runBacktest: (
    params: RunRequest,
    nodeContext: ReturnType<typeof useNodeContext>,
    onResult: (result: BacktestResult) => void,
  ): (() => void) => {
    const controller = new AbortController();

    const fail = (message: string) => {
      console.error('Backtest failed:', message);
      nodeContext.setRunError(message);
      nodeContext.settleRun(params.selected_agents || [], 'ERROR');
    };

    (async () => {
      nodeContext.setIsRunning(true);
      try {
        const response = await postJson('/backtest', params, controller.signal);

        await readEventStream(response, ({ type, data }) => {
          switch (type) {
            case 'start':
              nodeContext.resetAllNodes();
              nodeContext.setIsRunning(true);
              break;

            case 'progress': {
              const agent = data.agent as string | undefined;
              if (!agent) break;
              const status = String(data.status ?? '');
              nodeContext.updateAgentNode(statusKeyForAgent(agent), {
                status: progressNodeStatus(status),
                ticker: (data.ticker as string | null) ?? null,
                message: status,
                timestamp: data.timestamp as string | undefined,
              });
              break;
            }

            case 'complete':
              nodeContext.settleRun(params.selected_agents || [], 'COMPLETE');
              nodeContext.updateAgentNode(OUTPUT_KEY, { status: 'COMPLETE', message: 'Backtest complete' });
              onResult(data.data as unknown as BacktestResult);
              break;

            case 'error':
              fail((data.message as string) || 'The backtest failed without a message.');
              break;

            default:
              console.warn('Unknown event type:', type);
          }
        });
      } finally {
        nodeContext.setIsRunning(false);
      }
    })().catch((error: unknown) => {
      if (isAbortError(error)) return;
      fail(describe(error));
    });

    return () => controller.abort();
  },
};
