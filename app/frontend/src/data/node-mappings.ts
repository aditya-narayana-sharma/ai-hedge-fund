import { AppNode } from "@/nodes/types";
import { AgentItem } from "@/services/types";
import { INPUT_NODE_ID, OUTPUT_NODE_ID } from "./node-ids";

export interface NodeTypeDefinition {
  createNode: (position: { x: number, y: number }) => AppNode;
}

let nodeCounter = 0;

/** Distinct id per placed node, so adding an agent twice does not collide. */
function generateId(prefix: string): string {
  nodeCounter += 1;
  return `${prefix}-${nodeCounter}-${Date.now().toString(36)}`;
}

const staticNodeTypes: Record<string, NodeTypeDefinition> = {
  "Text Input": {
    createNode: (position): AppNode => ({
      id: INPUT_NODE_ID,
      type: "input-node",
      position,
      data: {
        name: "Input",
        description: "Start Node",
        status: "Idle",
      },
    }),
  },
  "Text Output": {
    createNode: (position): AppNode => ({
      id: OUTPUT_NODE_ID,
      type: "output-node",
      position,
      data: {
        name: "Output",
        description: "Output Node",
        status: "Idle",
      },
    }),
  },
};

/**
 * Build the sidebar-name to node-factory map for a fetched agent catalog.
 *
 * Agent nodes carry their catalog key in `data.agentKey`; the node id is
 * unique so the same agent can appear more than once on the canvas.
 */
export function createNodeTypeDefinitions(agents: AgentItem[]): Record<string, NodeTypeDefinition> {
  const agentNodeTypes = agents.reduce((acc, agent) => {
    acc[agent.display_name] = {
      createNode: (position): AppNode => ({
        id: generateId(agent.key),
        type: "agent-node",
        position,
        data: {
          name: agent.display_name,
          description: agent.description || "",
          status: "Idle",
          agentKey: agent.key,
        },
      }),
    };
    return acc;
  }, {} as Record<string, NodeTypeDefinition>);

  return { ...staticNodeTypes, ...agentNodeTypes };
}
