import { Edge, useReactFlow } from '@xyflow/react';
import { useCallback } from 'react';

import { AppNode } from '@/nodes/types';

/**
 * Save and restore the canvas.
 *
 * `resetFlow` used to be the only state transition, and it discarded
 * everything: a composed graph could not survive a reload. Flows are stored in
 * localStorage, and can be exported to and imported from a JSON file so they
 * can be shared or checked in.
 */

const STORAGE_KEY = 'ai-hedge-fund.flow';
const SCHEMA_VERSION = 1;

export interface SerializedFlow {
  version: number;
  savedAt: string;
  nodes: AppNode[];
  edges: Edge[];
}

function isSerializedFlow(value: unknown): value is SerializedFlow {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<SerializedFlow>;
  return Array.isArray(candidate.nodes) && Array.isArray(candidate.edges);
}

export function useFlowPersistence() {
  const { getNodes, getEdges, setNodes, setEdges, fitView } = useReactFlow();

  const serialize = useCallback(
    (): SerializedFlow => ({
      version: SCHEMA_VERSION,
      savedAt: new Date().toISOString(),
      nodes: getNodes() as AppNode[],
      edges: getEdges(),
    }),
    [getNodes, getEdges],
  );

  const restore = useCallback(
    (flow: SerializedFlow) => {
      setNodes(flow.nodes);
      setEdges(flow.edges);
      // Defer so React Flow measures the restored nodes first.
      window.setTimeout(() => fitView(), 0);
    },
    [setNodes, setEdges, fitView],
  );

  const saveToBrowser = useCallback(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(serialize()));
  }, [serialize]);

  const loadFromBrowser = useCallback((): boolean => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;

    try {
      const parsed: unknown = JSON.parse(raw);
      if (!isSerializedFlow(parsed)) return false;
      restore(parsed);
      return true;
    } catch {
      // A corrupt entry should not wedge the canvas on every load.
      window.localStorage.removeItem(STORAGE_KEY);
      return false;
    }
  }, [restore]);

  const hasSavedFlow = useCallback(() => window.localStorage.getItem(STORAGE_KEY) !== null, []);

  const exportToFile = useCallback(() => {
    const blob = new Blob([JSON.stringify(serialize(), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ai-hedge-fund-flow-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [serialize]);

  const importFromFile = useCallback(
    async (file: File): Promise<boolean> => {
      try {
        const parsed: unknown = JSON.parse(await file.text());
        if (!isSerializedFlow(parsed)) return false;
        restore(parsed);
        return true;
      } catch {
        return false;
      }
    },
    [restore],
  );

  return { saveToBrowser, loadFromBrowser, hasSavedFlow, exportToFile, importFromFile };
}
