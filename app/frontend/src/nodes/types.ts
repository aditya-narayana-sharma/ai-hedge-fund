import { MessageItem } from '@/contexts/node-context';
import type { BuiltInNode, Node } from '@xyflow/react';

export type NodeMessage = MessageItem;

export interface AgentNodeData extends Record<string, unknown> {
  name: string;
  description: string;
  status: string;
  /**
   * Backend identity of the agent this node represents. Node ids are unique
   * per instance, so the same agent can appear on the canvas twice; both
   * instances read their live status through this key.
   */
  agentKey: string;
  /** Risk manager and portfolio manager run on every request. */
  alwaysOn?: boolean;
}

export interface IoNodeData extends Record<string, unknown> {
  name: string;
  description: string;
  status: string;
}

export type AgentNode = Node<AgentNodeData, 'agent-node'>;
export type TextInputNode = Node<IoNodeData, 'input-node'>;
export type TextOutputNode = Node<IoNodeData, 'output-node'>;
export type AppNode = BuiltInNode | AgentNode | TextInputNode | TextOutputNode;
