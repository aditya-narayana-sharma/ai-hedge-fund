import type { EdgeTypes } from '@xyflow/react';

import { FlowEdge } from './flow-edge';

/** The edge type every connection uses; see flow-edge.tsx. */
export const DEFAULT_EDGE_TYPE = 'flow-edge';

export const edgeTypes = {
  'flow-edge': FlowEdge,
} satisfies EdgeTypes;
