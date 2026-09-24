import { MessageItem } from '@/contexts/node-context';
import type { BuiltInNode, Node } from '@xyflow/react';

export type NodeMessage = MessageItem;

// agentKey ties the node back to the catalog entry it was created from; the
// node id is unique so the same agent can be placed more than once.
export type AgentNode = Node<{ name: string, description: string, status: string, agentKey: string }, 'agent-node'>;
export type TextInputNode = Node<{ name: string, description: string, status: string }, 'input-node'>;
export type TextOutputNode = Node<{ name: string, description: string, status: string }, 'output-node'>;
export type AppNode = BuiltInNode | AgentNode | TextInputNode | TextOutputNode;
