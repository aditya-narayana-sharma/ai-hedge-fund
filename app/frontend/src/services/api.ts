import { NodeStatus, useNodeContext } from '@/contexts/node-context';
import { OUTPUT_NODE_ID } from '@/data/node-ids';
import { API_BASE_URL } from './config';
import {
  BacktestDayEventData,
  BacktestRequest,
  CompleteEventData,
  ErrorEventData,
  HedgeFundRequest,
  ProgressEventData,
} from './types';

/** Handlers for the events a streaming run emits. */
export interface RunStreamHandlers {
  onStart?: () => void;
  onProgress?: (event: ProgressEventData) => void;
  onBacktestDay?: (event: BacktestDayEventData) => void;
  onComplete?: (event: CompleteEventData) => void;
  onError?: (message: string) => void;
}

type SseEvent = { type: string; data: unknown };

function parseSseBlock(block: string): SseEvent | null {
  const eventTypeMatch = block.match(/^event: (.+)$/m);
  const dataMatch = block.match(/^data: (.+)$/m);
  if (!eventTypeMatch || !dataMatch) return null;

  try {
    return { type: eventTypeMatch[1], data: JSON.parse(dataMatch[1]) };
  } catch (err) {
    console.error('Error parsing SSE event:', err, 'Raw event:', block);
    return null;
  }
}

/**
 * POST a JSON body and consume the Server-Sent Event stream it returns.
 *
 * SSE over POST rules out EventSource, so the framing is parsed by hand:
 * events are separated by a blank line.
 */
function streamRun(path: string, body: unknown, handlers: RunStreamHandlers): () => void {
  const controller = new AbortController();

  fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async response => {
      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        throw new Error(detail ? `${response.status}: ${detail}` : `HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let done = false;

      while (!done) {
        const chunk = await reader.read();
        done = chunk.done;
        if (chunk.done) break;

        buffer += decoder.decode(chunk.value, { stream: true });

        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || ''; // Keep last partial event in buffer

        for (const block of blocks) {
          if (!block.trim()) continue;

          const event = parseSseBlock(block);
          if (!event) continue;

          switch (event.type) {
            case 'start':
              handlers.onStart?.();
              break;
            case 'progress':
              handlers.onProgress?.(event.data as ProgressEventData);
              break;
            case 'backtest_day':
              handlers.onBacktestDay?.(event.data as BacktestDayEventData);
              break;
            case 'complete':
              handlers.onComplete?.(event.data as CompleteEventData);
              break;
            case 'error':
              handlers.onError?.((event.data as ErrorEventData).message);
              break;
            default:
              console.warn('Unknown event type:', event.type);
          }
        }
      }
    })
    .catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      handlers.onError?.(error instanceof Error ? error.message : 'The run could not be completed');
    });

  return () => controller.abort();
}

export const api = {
  /**
   * Runs a hedge fund simulation and streams the results into node state.
   * @returns A function to abort the SSE connection
   */
  runHedgeFund: (
    params: HedgeFundRequest,
    nodeContext: ReturnType<typeof useNodeContext>
  ): (() => void) => {
    const statusKeys = () => [...params.selected_agents.map(key => `${key}_agent`)];

    return streamRun('/hedge-fund/run', params, {
      onStart: () => nodeContext.resetAllNodes(),
      onProgress: event => {
        if (!event.agent) return;
        const status: NodeStatus = event.status === 'Done' ? 'COMPLETE' : 'IN_PROGRESS';
        // The event's agent name is the key node state is stored under, so
        // the always-on risk and portfolio stages resolve like any analyst.
        nodeContext.updateAgentNode(event.agent, {
          status,
          ticker: event.ticker ?? null,
          message: event.status,
          timestamp: event.timestamp ?? undefined,
        });
      },
      onComplete: event => {
        if (event.data) {
          nodeContext.setOutputNodeData(event.data);
        }
        nodeContext.updateAgentNodes(statusKeys(), 'COMPLETE');
        nodeContext.updateAgentNode(OUTPUT_NODE_ID, {
          status: 'COMPLETE',
          message: 'Analysis complete',
        });
      },
      onError: message => {
        nodeContext.setRunError(message);
        nodeContext.updateAgentNodes(statusKeys(), 'ERROR');
        nodeContext.updateAgentNode(OUTPUT_NODE_ID, { status: 'ERROR', message });
      },
    });
  },

  /** Runs a backtest, streaming one event per simulated trading day. */
  runBacktest: (params: BacktestRequest, handlers: RunStreamHandlers): (() => void) =>
    streamRun('/backtest/run', params, handlers),
};
