import { ArrowDownToLine, ArrowUpFromLine, Bot, LucideIcon, ShieldCheck, Type } from 'lucide-react';

import { AgentItem } from '@/services/types';

import { ALWAYS_ON_STAGES } from './node-mappings';

// Define component items by group
export interface ComponentItem {
  name: string;
  icon: LucideIcon;
}

export interface ComponentGroup {
  name: string;
  icon: LucideIcon;
  iconColor: string;
  items: ComponentItem[];
}

/**
 * Build the sidebar from the agent catalog served by the backend.
 *
 * This used to be a module-level constant built from a hand-copied
 * src/data/agents.ts, so adding a Python agent never reached the UI.
 */
export function buildComponentGroups(agents: AgentItem[]): ComponentGroup[] {
  return [
    {
      name: 'agents',
      icon: Bot,
      iconColor: 'text-red-400',
      items: agents.map((agent) => ({ name: agent.display_name, icon: Bot })),
    },
    {
      // The backend appends both stages to every graph; putting them on the
      // canvas is what makes their progress visible.
      name: 'stages',
      icon: ShieldCheck,
      iconColor: 'text-orange-400',
      items: ALWAYS_ON_STAGES.map((stage) => ({ name: stage.display_name, icon: ShieldCheck })),
    },
    {
      name: 'inputs',
      icon: ArrowDownToLine,
      iconColor: 'text-blue-400',
      items: [{ name: 'Text Input', icon: Type }],
    },
    {
      name: 'outputs',
      icon: ArrowUpFromLine,
      iconColor: 'text-green-400',
      items: [{ name: 'Text Output', icon: Type }],
    },
  ];
}
