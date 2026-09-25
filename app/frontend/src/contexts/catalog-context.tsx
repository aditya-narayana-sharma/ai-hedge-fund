import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { fetchAgents, fetchModels } from '@/services/catalog';
import { AgentItem, ModelItem } from '@/services/types';

interface CatalogContextType {
  agents: AgentItem[];
  models: ModelItem[];
  defaultModel: ModelItem | null;
  isLoading: boolean;
  error: string | null;
  reload: () => void;
  getAgentByKey: (key: string) => AgentItem | undefined;
}

const CatalogContext = createContext<CatalogContextType | undefined>(undefined);

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    Promise.all([fetchAgents(), fetchModels()])
      .then(([loadedAgents, loadedModels]) => {
        if (cancelled) return;
        setAgents([...loadedAgents].sort((a, b) => a.order - b.order));
        setModels(loadedModels);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // The canvas is useless without the catalogs, so surface the reason
        // rather than rendering an empty sidebar.
        setError(err instanceof Error ? err.message : 'Could not reach the backend.');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const value = useMemo<CatalogContextType>(() => {
    const byKey = new Map(agents.map((agent) => [agent.key, agent]));
    return {
      agents,
      models,
      defaultModel: models.find((model) => model.model_name === 'gpt-4o') ?? models[0] ?? null,
      isLoading,
      error,
      reload,
      getAgentByKey: (key: string) => byKey.get(key),
    };
  }, [agents, models, isLoading, error, reload]);

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>;
}

export function useCatalog() {
  const context = useContext(CatalogContext);
  if (context === undefined) {
    throw new Error('useCatalog must be used within a CatalogProvider');
  }
  return context;
}
