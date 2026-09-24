import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';

import { ALWAYS_ON_AGENTS } from '@/data/node-ids';
import { fetchAgents, fetchModels } from '@/services/catalog';
import { AgentItem, ModelItem } from '@/services/types';

interface CatalogContextType {
  /** Analysts the user can wire into the graph. */
  agents: AgentItem[];
  /** Analysts plus the always-on risk and portfolio stages. */
  allAgents: AgentItem[];
  models: ModelItem[];
  isLoading: boolean;
  error: string | null;
}

const CatalogContext = createContext<CatalogContextType | undefined>(undefined);

/**
 * Loads the agent and model catalogs from the backend.
 *
 * They were previously re-declared by hand in TypeScript, so a Python-side
 * addition never reached the UI — and the copy had already lost Ollama.
 */
export function CatalogProvider({ children }: { children: ReactNode }) {
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    Promise.all([fetchAgents(controller.signal), fetchModels(controller.signal)])
      .then(([loadedAgents, loadedModels]) => {
        setAgents(loadedAgents);
        setModels(loadedModels);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Could not load the agent catalog');
      })
      .finally(() => setIsLoading(false));

    return () => controller.abort();
  }, []);

  const value = useMemo(
    () => ({
      agents,
      allAgents: [...agents, ...ALWAYS_ON_AGENTS],
      models,
      isLoading,
      error,
    }),
    [agents, models, isLoading, error]
  );

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}

export function useCatalog() {
  const context = useContext(CatalogContext);

  if (context === undefined) {
    throw new Error('useCatalog must be used within a CatalogProvider');
  }

  return context;
}
