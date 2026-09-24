import { ModelSelector } from '@/components/ui/llm-selector';
import { useReactFlow, type NodeProps } from '@xyflow/react';
import { AlertTriangle, Bot, Loader2, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useCatalog } from '@/contexts/catalog-context';
import { useNodeContext } from '@/contexts/node-context';
import { OUTPUT_NODE_ID, PORTFOLIO_MANAGER_KEY, RISK_MANAGER_KEY } from '@/data/node-mappings';
import { api } from '@/services/api';
import { BacktestResult, ModelItem } from '@/services/types';
import { type TextInputNode } from '../types';
import { getAgentKeysInCompletePaths } from '../utils';
import { BacktestDialog } from './backtest-dialog';
import { NodeShell } from './node-shell';

type RunMode = 'analysis' | 'backtest';

export function TextInputNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<TextInputNode>) {
  const [tickers, setTickers] = useState('');
  const [mode, setMode] = useState<RunMode>('analysis');
  const [selectedModel, setSelectedModel] = useState<ModelItem | null>(null);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [isBacktestOpen, setIsBacktestOpen] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const nodeContext = useNodeContext();
  const { resetAllNodes, agentNodeData, runError } = nodeContext;
  const { models, defaultModel, isLoading: catalogLoading, error: catalogError } = useCatalog();
  const { getNodes, getEdges } = useReactFlow();
  const abortRef = useRef<(() => void) | null>(null);

  const isProcessing = Object.values(agentNodeData).some((agent) => agent.status === 'IN_PROGRESS');

  // Adopt the catalog's default once it arrives, without clobbering a choice
  // the user has already made.
  useEffect(() => {
    setSelectedModel((current) => current ?? defaultModel);
  }, [defaultModel]);

  useEffect(() => {
    return () => {
      abortRef.current?.();
    };
  }, []);

  const handleTickersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTickers(e.target.value);
  };

  const handlePlay = () => {
    setLocalError(null);
    resetAllNodes();
    abortRef.current?.();

    const tickerList = tickers
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    if (tickerList.length === 0) {
      setLocalError('Enter at least one ticker.');
      return;
    }

    // Resolve agents along complete Input -> ... -> Output paths rather than
    // only the agents one hop from the input, so chained topologies work and
    // an unterminated branch is not silently submitted.
    const agentKeys = getAgentKeysInCompletePaths({
      startNodeId: id,
      endNodeId: OUTPUT_NODE_ID,
      nodes: getNodes(),
      edges: getEdges(),
      // The backend appends these two stages itself and rejects them as
      // analyst keys, so their canvas nodes are display-only.
      exclude: [RISK_MANAGER_KEY, PORTFOLIO_MANAGER_KEY],
    });

    if (agentKeys.length === 0) {
      setLocalError('Connect at least one agent along a path from Input to Output.');
      return;
    }

    const params = {
      tickers: tickerList,
      selected_agents: agentKeys,
      model_name: selectedModel?.model_name || undefined,
      model_provider: selectedModel?.provider || undefined,
    };

    abortRef.current =
      mode === 'backtest'
        ? api.runBacktest(params, nodeContext, (result) => {
            setBacktestResult(result);
            setIsBacktestOpen(true);
          })
        : api.runHedgeFund(params, nodeContext);
  };

  const errorMessage = localError ?? runError ?? catalogError;

  return (
    <TooltipProvider>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<Bot className="h-5 w-5" />}
        name={data.name || 'Custom Component'}
        description={data.description}
        hasLeftHandle={false}
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
            <div className="flex flex-col gap-4">
              <Tabs value={mode} onValueChange={(value) => setMode(value as RunMode)}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="analysis">Analysis</TabsTrigger>
                  <TabsTrigger value="backtest">Backtest</TabsTrigger>
                </TabsList>
              </Tabs>

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
                    disabled={isProcessing || !tickers.trim() || catalogLoading}
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
                  value={selectedModel?.model_name || ''}
                  onChange={setSelectedModel}
                  placeholder={catalogLoading ? 'Loading models…' : 'Select a model...'}
                />
              </div>

              {errorMessage && (
                <div className="flex items-start gap-2 rounded border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-400">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                  <span className="break-words">{errorMessage}</span>
                </div>
              )}

              {backtestResult && (
                <Button variant="secondary" size="sm" onClick={() => setIsBacktestOpen(true)}>
                  View backtest report
                </Button>
              )}
            </div>
          </div>
        </CardContent>

        <BacktestDialog
          isOpen={isBacktestOpen}
          onOpenChange={setIsBacktestOpen}
          result={backtestResult}
        />
      </NodeShell>
    </TooltipProvider>
  );
}
