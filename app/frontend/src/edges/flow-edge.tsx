import { BaseEdge, getBezierPath, type EdgeProps, type Node, useNodes } from '@xyflow/react';

import { useNodeContext } from '@/contexts/node-context';
import { progressKey } from '@/data/node-ids';

/**
 * A connection that animates while the agent it feeds is running, so the
 * canvas shows where work is happening rather than only which nodes are lit.
 */
export function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  target,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const nodes = useNodes();
  const { agentNodeData } = useNodeContext();

  const targetNode = nodes.find((node: Node) => node.id === target);
  const agentKey = targetNode?.type === 'agent-node' ? (targetNode.data as { agentKey?: string }).agentKey : undefined;
  const isActive = agentKey ? agentNodeData[progressKey(agentKey)]?.status === 'IN_PROGRESS' : false;

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      markerEnd={markerEnd}
      style={{
        ...style,
        strokeWidth: isActive ? 2 : 1,
        stroke: isActive ? 'hsl(var(--primary))' : undefined,
        strokeDasharray: isActive ? '6 4' : undefined,
        animation: isActive ? 'dash 0.6s linear infinite' : undefined,
      }}
    />
  );
}
