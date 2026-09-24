import { API_BASE_URL } from './config';
import { AgentItem, ModelItem } from './types';

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`GET ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

/** The analysts the backend can run, from ANALYST_CONFIG. */
export function fetchAgents(signal?: AbortSignal): Promise<AgentItem[]> {
  return getJson<AgentItem[]>('/agents', signal);
}

/** Every selectable model, cloud and local. */
export function fetchModels(signal?: AbortSignal): Promise<ModelItem[]> {
  return getJson<ModelItem[]>('/models', signal);
}
