import type { EdgeTypes } from '@xyflow/react';

import { StatusEdge } from './status-edge';

export const STATUS_EDGE_TYPE = 'status-edge';

export const edgeTypes = {
  [STATUS_EDGE_TYPE]: StatusEdge,
} satisfies EdgeTypes;
