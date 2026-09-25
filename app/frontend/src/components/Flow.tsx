import {
  Background,
  ColorMode,
  Connection,
  Controls,
  Edge,
  MarkerType,
  Panel,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState
} from '@xyflow/react';
import { useCallback, useEffect, useRef, useState } from 'react';

import '@xyflow/react/dist/style.css';

import { useFlowPersistence } from '@/hooks/use-flow-persistence';
import { AppNode } from '@/nodes/types';
import { STATUS_EDGE_TYPE, edgeTypes } from '../edges';
import { initialNodes, nodeTypes } from '../nodes';
import { Button } from './ui/button';

type FlowProps = {
  className?: string;
};

export function Flow({ className = '' }: FlowProps) {
  const [colorMode] = useState<ColorMode>('dark');
  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const proOptions = { hideAttribution: true };

  const { saveToBrowser, loadFromBrowser, hasSavedFlow, exportToFile, importFromFile } = useFlowPersistence();

  // Restore the last canvas on first render so a reload is not destructive.
  useEffect(() => {
    loadFromBrowser();
    // Intentionally once, on mount: later calls are user-initiated.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = useCallback((message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 2500);
  }, []);

  // Connect two nodes with marker
  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        ...connection,
        id: `edge-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: STATUS_EDGE_TYPE,
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      setEdges((eds) => addEdge(newEdge, eds));
    },
    [setEdges]
  );

  // Reset the flow to initial state
  const resetFlow = useCallback(() => {
    setNodes(initialNodes);
    setEdges([]);
  }, [setNodes, setEdges]);

  const handleSave = useCallback(() => {
    saveToBrowser();
    flash('Flow saved');
  }, [saveToBrowser, flash]);

  const handleLoad = useCallback(() => {
    flash(loadFromBrowser() ? 'Flow restored' : 'No saved flow found');
  }, [loadFromBrowser, flash]);

  const handleImport = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = ''; // allow re-importing the same file
      if (!file) return;
      flash((await importFromFile(file)) ? 'Flow imported' : 'That file is not a saved flow');
    },
    [importFromFile, flash]
  );

  return (
    <div className={`w-full h-full ${className}`}>
      <ReactFlow
        nodes={nodes}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        edges={edges}
        edgeTypes={edgeTypes}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        colorMode={colorMode}
        proOptions={proOptions}
        fitView
      >
        <Background gap={13}/>
        <Controls 
          position="bottom-center" 
          orientation="horizontal" 
          style={{ bottom: 20 }}
        />
        <Panel position="top-right">
          <div className="flex items-center gap-2">
            {notice && <span className="text-xs text-muted-foreground">{notice}</span>}
            <Button variant="secondary" size="sm" onClick={handleSave}>
              Save
            </Button>
            <Button variant="secondary" size="sm" onClick={handleLoad} disabled={!hasSavedFlow()}>
              Load
            </Button>
            <Button variant="secondary" size="sm" onClick={exportToFile}>
              Export
            </Button>
            <Button variant="secondary" size="sm" onClick={() => fileInputRef.current?.click()}>
              Import
            </Button>
            <Button onClick={resetFlow}>Reset Flow</Button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={handleImport}
            />
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
