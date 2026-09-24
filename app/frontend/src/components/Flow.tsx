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
import { useCallback, useRef, useState } from 'react';

import '@xyflow/react/dist/style.css';

import { AppNode } from '@/nodes/types';
import { DEFAULT_EDGE_TYPE, edgeTypes } from '../edges';
import { clearSavedFlow, loadSavedFlow, useFlowPersistence } from '../hooks/use-flow-persistence';
import { initialNodes, nodeTypes } from '../nodes';
import { Button } from './ui/button';

type FlowProps = {
  className?: string;
};

const restoredFlow = loadSavedFlow();

export function Flow({ className = '' }: FlowProps) {
  const [colorMode] = useState<ColorMode>('dark');
  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>(restoredFlow?.nodes ?? initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(restoredFlow?.edges ?? []);
  const [isInitialized, setIsInitialized] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const proOptions = { hideAttribution: true };

  const { exportFlow, importFlow } = useFlowPersistence(nodes, edges);

  // Initialize the flow when it first renders
  const onInit = useCallback(() => {
    if (!isInitialized) {
      setIsInitialized(true);
    }
  }, [isInitialized]);

  // Connect two nodes with marker
  const onConnect = useCallback(
    (connection: Connection) => {
      // Create a new edge with a marker and unique ID
      const newEdge: Edge = {
        ...connection,
        id: `edge-${Date.now()}`, // Add unique ID
        type: DEFAULT_EDGE_TYPE,
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
    clearSavedFlow();
  }, [setNodes, setEdges]);

  const handleImport = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (!file) return;

      try {
        const saved = await importFlow(file);
        setNodes(saved.nodes);
        setEdges(saved.edges);
        setImportError(null);
      } catch (err) {
        setImportError(err instanceof Error ? err.message : 'Could not read that file.');
      }
    },
    [importFlow, setNodes, setEdges]
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
        onInit={onInit}
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
            {importError && <span className="text-xs text-red-400">{importError}</span>}
            <Button variant="secondary" onClick={exportFlow}>
              Export
            </Button>
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
              Import
            </Button>
            <Button onClick={resetFlow}>
              Reset Flow
            </Button>
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
