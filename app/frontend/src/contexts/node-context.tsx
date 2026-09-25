import { createContext, ReactNode, useCallback, useContext, useState } from 'react';

import { HedgeFundResult } from '@/services/types';

export type NodeStatus = 'IDLE' | 'IN_PROGRESS' | 'COMPLETE' | 'ERROR';

// Message history item
export interface MessageItem {
  timestamp: string;
  message: string;
  ticker: string | null;
}

// Agent node state structure
export interface AgentNodeData {
  status: NodeStatus;
  ticker: string | null;
  message: string;
  lastUpdated: number;
  messages: MessageItem[];
  timestamp?: string;
}

// Data structure for the output node data (from complete event)
export type OutputNodeData = HedgeFundResult;

// Default agent node state
const DEFAULT_AGENT_NODE_STATE: AgentNodeData = {
  status: 'IDLE',
  ticker: null,
  message: '',
  messages: [],
  lastUpdated: Date.now()
};

interface NodeContextType {
  agentNodeData: Record<string, AgentNodeData>;
  outputNodeData: OutputNodeData | null;
  /** Message from the SSE `error` event, or a transport failure. */
  runError: string | null;
  /** Owned by the request, not by scanning node status. Cleared on every terminal path. */
  isRunning: boolean;
  setIsRunning: (running: boolean) => void;
  /** Finish a run without leaving an unrecognised progress key stuck IN_PROGRESS. */
  settleRun: (selectedAgentKeys: string[], outcome: 'COMPLETE' | 'ERROR') => void;
  updateAgentNode: (nodeId: string, data: Partial<AgentNodeData> | NodeStatus) => void;
  updateAgentNodes: (nodeIds: string[], status: NodeStatus) => void;
  setOutputNodeData: (data: OutputNodeData) => void;
  setRunError: (message: string | null) => void;
  resetAllNodes: () => void;
}

const NodeContext = createContext<NodeContextType | undefined>(undefined);

export function NodeProvider({ children }: { children: ReactNode }) {
  const [agentNodeData, setAgentNodeData] = useState<Record<string, AgentNodeData>>({});
  const [outputNodeData, setOutputNodeData] = useState<OutputNodeData | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const settleRun = useCallback((selectedAgentKeys: string[], outcome: 'COMPLETE' | 'ERROR') => {
    const selected = new Set(selectedAgentKeys);
    setIsRunning(false);
    setAgentNodeData((prev) => {
      const next: Record<string, AgentNodeData> = { ...prev };
      for (const [key, value] of Object.entries(next)) {
        // An analyst that reported Failed/Warning stays red on an otherwise
        // successful run. Blanket COMPLETE used to paint over that.
        if (value.status === 'ERROR') continue;
        if (selected.has(key) || value.status === 'IN_PROGRESS') {
          next[key] = { ...value, status: outcome, lastUpdated: Date.now() };
        }
      }
      return next;
    });
  }, []);

  const updateAgentNode = useCallback((nodeId: string, data: Partial<AgentNodeData> | NodeStatus) => {
    // Handle string status shorthand (just passing a status string)
    if (typeof data === 'string') {
      setAgentNodeData(prev => {
        const existingNode = prev[nodeId] || { ...DEFAULT_AGENT_NODE_STATE };
        return {
          ...prev,
          [nodeId]: {
            ...existingNode,
            status: data,
            lastUpdated: Date.now()
          }
        };
      });
      return;
    }

    // Handle data object - full update
    setAgentNodeData(prev => {
      const existingNode = prev[nodeId] || { ...DEFAULT_AGENT_NODE_STATE };
      const newMessages = [...existingNode.messages];
      
      // Add message to history if it's new
      if (data.message && data.message !== existingNode.message) {
        newMessages.push({
          timestamp: data.timestamp || new Date().toISOString(),
          message: data.message,
          ticker: data.ticker || existingNode.ticker
        });
      }
      
      return {
        ...prev,
        [nodeId]: {
          ...existingNode,
          ...data,
          messages: newMessages,
          lastUpdated: Date.now()
        }
      };
    });
  }, []);

  const updateAgentNodes = useCallback((nodeIds: string[], status: NodeStatus) => {
    if (nodeIds.length === 0) return;
    
    setAgentNodeData(prev => {
      const newStates = { ...prev };
      
      nodeIds.forEach(id => {
        newStates[id] = {
          ...(newStates[id] || { ...DEFAULT_AGENT_NODE_STATE }),
          status,
          lastUpdated: Date.now()
        };
      });
      
      return newStates;
    });
  }, []);

  const resetAllNodes = useCallback(() => {
    setAgentNodeData({});
    setOutputNodeData(null);
    setRunError(null);
    setIsRunning(false);
  }, []);

  return (
    <NodeContext.Provider
      value={{
        agentNodeData,
        outputNodeData,
        runError,
        isRunning,
        setIsRunning,
        settleRun,
        updateAgentNode,
        updateAgentNodes,
        setOutputNodeData,
        setRunError,
        resetAllNodes,
      }}
    >
      {children}
    </NodeContext.Provider>
  );
}

export function useNodeContext() {
  const context = useContext(NodeContext);
  
  if (context === undefined) {
    throw new Error('useNodeContext must be used within a NodeProvider');
  }
  
  return context;
} 