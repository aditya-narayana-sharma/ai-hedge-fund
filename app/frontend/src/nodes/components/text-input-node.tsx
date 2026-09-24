import { ModelSelector } from '@/components/ui/llm-selector';
import { useReactFlow, type NodeProps } from '@xyflow/react';
import { Bot, Loader2, Play } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useCatalog } from '@/contexts/catalog-context';
import { useNodeContext } from '@/contexts/node-context';
import { isAlwaysOnAgent, OUTPUT_NODE_ID } from '@/data/node-ids';
import { getNodesInCompletePaths } from '@/nodes/utils';
import { api } from '@/services/api';
import { ModelItem } from '@/services/types';
import { type AgentNode, type TextInputNode } from '../types';
import { NodeShell } from './node-shell';

export function TextInputNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<TextInputNode>) {
  const [tickers, setTickers] = useState('');
  const [selectedModel, setSelectedModel] = useState<ModelItem | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const nodeContext = useNodeContext();
  const { resetAllNodes, agentNodeData, runError } = nodeContext;
  const { models, isLoading: isCatalogLoading, error: catalogError } = useCatalog();
  const { getNodes, getEdges } = useReactFlow();
  const abortControllerRef = useRef<(() => void) | null>(null);

  // Default to GPT-4o when the catalog arrives, or the first model offered.
  const defaultModel = useMemo(
    () => models.find(model => model.model_name === 'gpt-4o') ?? models[0] ?? null,
    [models]
  );

  useEffect(() => {
    setSelectedModel(current => current ?? defaultModel);
  }, [defaultModel]);

  // Check if any agent is in progress
  const isProcessing = Object.values(agentNodeData).some(
    agent => agent.status === 'IN_PROGRESS'
  );

  // Clean up SSE connection on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current();
      }
    };
  }, []);

  const handleTickersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTickers(e.target.value);
  };

  const handlePlay = () => {
    setValidationError(null);

    const tickerList = tickers.split(',').map(t => t.trim()).filter(Boolean);
    if (tickerList.length === 0) {
      setValidationError('Enter at least one ticker.');
      return;
    }

    // Only agents on a complete input -> ... -> output path take part, so a
    // chained topology works and a dangling agent does not.
    const nodes = getNodes();
    const nodeIdsInPaths = getNodesInCompletePaths({
      startNodeId: id,
      endNodeId: OUTPUT_NODE_ID,
      nodes,
      edges: getEdges(),
    });

    const selectedAgents = Array.from(
      new Set(
        nodes
          .filter((node): node is AgentNode => node.type === 'agent-node' && nodeIdsInPaths.has(node.id))
          .map(node => node.data.agentKey)
          // The backend appends these to every graph; sending them would be
          // rejected as unknown analysts.
          .filter(agentKey => !isAlwaysOnAgent(agentKey))
      )
    );

    if (selectedAgents.length === 0) {
      setValidationError('Connect at least one agent along a path from Input to Output.');
      return;
    }

    if (!selectedModel) {
      setValidationError('Select a model first.');
      return;
    }

    // Reset all nodes to IDLE, then clean up any existing connection
    resetAllNodes();
    if (abortControllerRef.current) {
      abortControllerRef.current();
    }

    abortControllerRef.current = api.runHedgeFund(
      {
        tickers: tickerList,
        selected_agents: selectedAgents,
        model_name: selectedModel.model_name,
        model_provider: selectedModel.provider,
      },
      // Pass the node status context to the API
      nodeContext
    );
  };

  const errorMessage = validationError ?? runError ?? catalogError;

  return (
    <TooltipProvider>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<Bot className="h-5 w-5" />}
        name={data.name || "Custom Component"}
        description={data.description}
        hasLeftHandle={false}
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-muted-foreground flex items-center gap-1">
                  <Tooltip delayDuration={200}>
                    <TooltipTrigger asChild>
                      <span>Tickers</span>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      You can add multiple tickers using commas (AAPL,NVDA,TSLA)
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter tickers"
                    value={tickers}
                    onChange={handleTickersChange}
                  />
                  <Button 
                    size="icon" 
                    variant="secondary"
                    className="flex-shrink-0 transition-all duration-200 hover:bg-primary hover:text-primary-foreground active:scale-95"
                    onClick={handlePlay}
                    disabled={isProcessing || isCatalogLoading || !tickers.trim()}
                  >
                    {isProcessing ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Play className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-muted-foreground flex items-center gap-1">
                  Model
                </div>
                <ModelSelector
                  models={models}
                  value={selectedModel?.model_name || ""}
                  onChange={setSelectedModel}
                  placeholder={isCatalogLoading ? "Loading models..." : "Select a model..."}
                />
              </div>

              {errorMessage && (
                <div className="text-subtitle text-red-400 break-words" role="alert">
                  {errorMessage}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </NodeShell>
    </TooltipProvider>
  );
}
