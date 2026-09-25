import { BaseEdge, EdgeProps, getBezierPath } from '@xyflow/react';
import { useReactFlow } from '@xyflow/react';

import { useNodeContext } from '@/contexts/node-context';

/**
 * An edge that reflects the state of the agent it leaves.
 *
 * Node borders already animate while an agent runs, but the wiring between
 * them stayed inert, so on a busy canvas it was not obvious which branch was
 * live. This is the custom edge type the `edges/index.ts` placeholder was
 * reserved for.
 */
export function StatusEdge({
  id,
  source,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const { agentNodeData } = useNodeContext();
  const { getNode } = useReactFlow();

  const sourceNode = getNode(source);
  const agentKey = (sourceNode?.data as { agentKey?: string } | undefined)?.agentKey;
  const status = agentKey ? agentNodeData[agentKey]?.status : undefined;

  const stroke = status === 'IN_PROGRESS' ? '#d29922' : status === 'ERROR' ? '#f85149' : status === 'COMPLETE' ? '#3fb950' : undefined;

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      markerEnd={markerEnd}
      style={{
        ...style,
        ...(stroke ? { stroke, strokeWidth: 2 } : {}),
        // Dashes only move while work is in flight.
        ...(status === 'IN_PROGRESS' ? { strokeDasharray: 6, animation: 'dashdraw 0.6s linear infinite' } : {}),
      }}
    />
  );
}
