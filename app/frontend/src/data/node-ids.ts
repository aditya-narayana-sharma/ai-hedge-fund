import { AgentItem } from '@/services/types';

/**
 * The one place that knows how backend agent names line up with canvas nodes.
 *
 * api.ts used to guess by stripping `_agent`, which produced
 * `risk_management` — matching no node — and wrote output status to an id
 * (`output`) that no node has ever had.
 */

export const INPUT_NODE_ID = 'text-input-node';
export const OUTPUT_NODE_ID = 'text-output-node';

export const RISK_MANAGER_KEY = 'risk_management_agent';
export const PORTFOLIO_MANAGER_KEY = 'portfolio_manager';
export const SYSTEM_KEY = 'system';

/**
 * Stages app/backend/services/graph.py appends to every graph regardless of
 * what the user selected, so they are never part of `selected_agents`.
 */
export const ALWAYS_ON_AGENTS: AgentItem[] = [
  {
    key: RISK_MANAGER_KEY,
    display_name: 'Risk Manager',
    description: 'Position Sizing',
    order: 1000,
  },
  {
    key: PORTFOLIO_MANAGER_KEY,
    display_name: 'Portfolio Manager',
    description: 'Final Orders',
    order: 1001,
  },
];

const ALWAYS_ON_KEYS = new Set(ALWAYS_ON_AGENTS.map(agent => agent.key));

export function isAlwaysOnAgent(agentKey: string): boolean {
  return ALWAYS_ON_KEYS.has(agentKey);
}

/**
 * The name a given agent reports progress under. Analysts are registered as
 * `<key>_agent`; the always-on stages report under their own key.
 */
export function progressKey(agentKey: string): string {
  return isAlwaysOnAgent(agentKey) ? agentKey : `${agentKey}_agent`;
}
