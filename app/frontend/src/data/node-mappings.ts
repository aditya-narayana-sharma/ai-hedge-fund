import { AgentItem } from '@/services/types';
import { AppNode } from '@/nodes/types';

/**
 * The single place that knows how backend agent names, canvas node ids and
 * node-status keys relate.
 *
 * Previously api.ts guessed with `agentName.replace('_agent', '')`, which
 * produced `risk_management` for `risk_management_agent` and matched nothing,
 * and wrote output status to the id `'output'` while the real node id was
 * `text-output-node`. Both writes were dead.
 */

/** Node ids for the singleton nodes. */
export const INPUT_NODE_ID = 'text-input-node';
export const OUTPUT_NODE_ID = 'text-output-node';

/** Status keys for the stages the backend always runs, plus its own messages. */
export const RISK_MANAGER_KEY = 'risk_management_agent';
export const PORTFOLIO_MANAGER_KEY = 'portfolio_manager';
export const SYSTEM_KEY = 'system';
export const BACKTESTER_KEY = 'backtester';
export const OUTPUT_KEY = 'output';

/** Backend agent names that are already their own status key. */
const LITERAL_KEYS = new Set([RISK_MANAGER_KEY, PORTFOLIO_MANAGER_KEY, SYSTEM_KEY, BACKTESTER_KEY]);

const AGENT_SUFFIX = '_agent';

/**
 * Convert a backend progress `agent` field into the status key the canvas
 * stores it under. Analysts arrive as `<key>_agent`; the always-on stages and
 * system messages arrive verbatim.
 */
export function statusKeyForAgent(agentName: string): string {
  if (LITERAL_KEYS.has(agentName)) return agentName;
  return agentName.endsWith(AGENT_SUFFIX) ? agentName.slice(0, -AGENT_SUFFIX.length) : agentName;
}

/** Stages the backend runs on every request, whether or not they are on the canvas. */
export const ALWAYS_ON_STAGES: AgentItem[] = [
  {
    key: RISK_MANAGER_KEY,
    display_name: 'Risk Manager',
    description: 'Sizes every position against net liquidation value. Always runs.',
    order: 100,
  },
  {
    key: PORTFOLIO_MANAGER_KEY,
    display_name: 'Portfolio Manager',
    description: 'Turns analyst signals into orders. Always runs.',
    order: 101,
  },
];

let nodeSequence = 0;

/** Distinct id per instance, so adding the same agent twice does not collide. */
export function generateNodeId(prefix: string): string {
  nodeSequence += 1;
  return `${prefix}-${Date.now().toString(36)}-${nodeSequence}`;
}

export function createInputNode(position: { x: number; y: number }): AppNode {
  return {
    id: INPUT_NODE_ID,
    type: 'input-node',
    position,
    data: { name: 'Input', description: 'Start Node', status: 'Idle' },
  };
}

export function createOutputNode(position: { x: number; y: number }): AppNode {
  return {
    id: OUTPUT_NODE_ID,
    type: 'output-node',
    position,
    data: { name: 'Output', description: 'Output Node', status: 'Idle' },
  };
}

export function createAgentNode(agent: AgentItem, position: { x: number; y: number }): AppNode {
  return {
    // Unique per instance; `agentKey` carries the backend identity that used
    // to be encoded in the id.
    id: generateNodeId(agent.key),
    type: 'agent-node',
    position,
    data: {
      name: agent.display_name,
      description: agent.description || '',
      status: 'Idle',
      agentKey: agent.key,
      alwaysOn: agent.key === RISK_MANAGER_KEY || agent.key === PORTFOLIO_MANAGER_KEY,
    },
  };
}

/** Build the sidebar-name to node-factory map from a fetched agent catalog. */
export function buildNodeFactories(agents: AgentItem[]): Record<string, (position: { x: number; y: number }) => AppNode> {
  const factories: Record<string, (position: { x: number; y: number }) => AppNode> = {
    'Text Input': createInputNode,
    'Text Output': createOutputNode,
  };

  for (const agent of [...agents, ...ALWAYS_ON_STAGES]) {
    factories[agent.display_name] = (position) => createAgentNode(agent, position);
  }

  return factories;
}
