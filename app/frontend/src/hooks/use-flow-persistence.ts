import { type Edge } from '@xyflow/react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { AppNode } from '@/nodes/types';

const STORAGE_KEY = 'ai-hedge-fund.flow';
const SAVE_DEBOUNCE_MS = 400;

export interface SavedFlow {
  version: 1;
  nodes: AppNode[];
  edges: Edge[];
}

function isSavedFlow(value: unknown): value is SavedFlow {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<SavedFlow>;
  return Array.isArray(candidate.nodes) && Array.isArray(candidate.edges);
}

/** Read the last autosaved graph, or null when there is none to restore. */
export function loadSavedFlow(): SavedFlow | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isSavedFlow(parsed) ? parsed : null;
  } catch (err) {
    console.warn('Could not restore the saved flow', err);
    return null;
  }
}

export function clearSavedFlow(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

/**
 * Autosave the graph to localStorage and expose file export/import.
 *
 * Reset used to discard the canvas with no way back, and nothing survived a
 * page reload.
 */
export function useFlowPersistence(nodes: AppNode[], edges: Edge[]) {
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      try {
        const payload: SavedFlow = { version: 1, nodes, edges };
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        setLastSavedAt(Date.now());
      } catch (err) {
        console.warn('Could not save the flow', err);
      }
    }, SAVE_DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [nodes, edges]);

  const exportFlow = useCallback(() => {
    const payload: SavedFlow = { version: 1, nodes, edges };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `hedge-fund-flow-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [nodes, edges]);

  const importFlow = useCallback(async (file: File): Promise<SavedFlow> => {
    const parsed: unknown = JSON.parse(await file.text());
    if (!isSavedFlow(parsed)) {
      throw new Error('That file is not a saved flow.');
    }
    return parsed;
  }, []);

  return { lastSavedAt, exportFlow, importFlow };
}
