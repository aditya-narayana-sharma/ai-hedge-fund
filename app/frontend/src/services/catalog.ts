import { AgentItem, ModelItem } from '@/services/types';

import { API_BASE_URL } from './config';

/**
 * Reads the agent and model catalogs from the backend.
 *
 * These used to be hand-copied into src/data/agents.ts and src/data/models.ts
 * even though src/utils/analysts.py calls itself the single source of truth.
 * The mirror had already drifted: it omitted the Ollama provider entirely,
 * which made the whole local-LLM path unreachable from the web app.
 */
async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchAgents(): Promise<AgentItem[]> {
  return getJson<AgentItem[]>('/agents');
}

export function fetchModels(): Promise<ModelItem[]> {
  return getJson<ModelItem[]>('/models');
}
