import { useReactFlow, XYPosition } from '@xyflow/react';
import { createContext, ReactNode, useCallback, useContext, useMemo } from 'react';

import { buildNodeFactories } from '@/data/node-mappings';

import { useCatalog } from './catalog-context';

interface FlowContextType {
  addNodeFromComponent: (componentName: string) => void;
}

const FlowContext = createContext<FlowContextType | null>(null);

export function useFlowContext() {
  const context = useContext(FlowContext);
  if (!context) {
    throw new Error('useFlowContext must be used within a FlowProvider');
  }
  return context;
}

interface FlowProviderProps {
  children: ReactNode;
}

export function FlowProvider({ children }: FlowProviderProps) {
  const reactFlowInstance = useReactFlow();
  const { agents } = useCatalog();

  const nodeFactories = useMemo(() => buildNodeFactories(agents), [agents]);

  // Add a node to the flow from a component in the sidebar
  const addNodeFromComponent = useCallback(
    (componentName: string) => {
      const createNode = nodeFactories[componentName];
      if (!createNode) {
        console.warn(`No node type definition found for component: ${componentName}`);
        return;
      }

      // Calculate center viewport position
      let position: XYPosition = { x: 100, y: 100 }; // Default position

      try {
        const { zoom, x, y } = reactFlowInstance.getViewport();
        position = {
          x: (window.innerWidth / 2 - x) / zoom,
          y: (window.innerHeight / 2 - y) / zoom,
        };
      } catch (err) {
        console.warn('Could not get viewport', err);
      }

      // Add some randomness to prevent perfect overlap if multiple nodes are added
      position.x += Math.random() * 100 - 50;
      position.y = 0;

      reactFlowInstance.setNodes((nodes) => [...nodes, createNode(position)]);
    },
    [nodeFactories, reactFlowInstance],
  );

  const value = { addNodeFromComponent };

  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>;
}
