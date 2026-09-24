import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Bot,
  LucideIcon,
  Shield,
  Type,
  Wallet
} from 'lucide-react';
import { AgentItem } from '@/services/types';
import { PORTFOLIO_MANAGER_KEY, RISK_MANAGER_KEY } from './node-ids';

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

const ALWAYS_ON_ICONS: Record<string, LucideIcon> = {
  [RISK_MANAGER_KEY]: Shield,
  [PORTFOLIO_MANAGER_KEY]: Wallet,
};

/** Build the sidebar from a fetched agent catalog. */
export function getComponentGroups(agents: AgentItem[]): ComponentGroup[] {
  return [
    {
      name: "agents",
      icon: Bot,
      iconColor: "text-red-400",
      items: agents.map(agent => ({
        name: agent.display_name,
        icon: ALWAYS_ON_ICONS[agent.key] ?? Bot
      }))
    },
    {
      name: "inputs",
      icon: ArrowDownToLine,
      iconColor: "text-blue-400",
      items: [
        { name: "Text Input", icon: Type },
      ]
    },
    {
      name: "outputs",
      icon: ArrowUpFromLine,
      iconColor: "text-green-400",
      items: [
        { name: "Text Output", icon: Type },
      ]
    },
  ];
}
