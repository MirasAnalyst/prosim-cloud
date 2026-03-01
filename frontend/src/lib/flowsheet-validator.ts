import type { Node, Edge } from '@xyflow/react';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export function validateFlowsheet(nodes: Node[], edges: Edge[]): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Duplicate node IDs
  const nodeIds = new Set<string>();
  for (const n of nodes) {
    if (nodeIds.has(n.id)) {
      errors.push(`Duplicate node ID: ${n.id}`);
    }
    nodeIds.add(n.id);
  }

  // Duplicate edge IDs
  const edgeIds = new Set<string>();
  for (const e of edges) {
    if (edgeIds.has(e.id)) {
      errors.push(`Duplicate edge ID: ${e.id}`);
    }
    edgeIds.add(e.id);
  }

  // Orphan edges
  for (const e of edges) {
    if (e.source && !nodeIds.has(e.source)) {
      errors.push(`Edge ${e.id} references nonexistent source: ${e.source}`);
    }
    if (e.target && !nodeIds.has(e.target)) {
      errors.push(`Edge ${e.id} references nonexistent target: ${e.target}`);
    }
  }

  // Self-loops
  for (const e of edges) {
    if (e.source && e.source === e.target) {
      errors.push(`Self-loop on edge ${e.id}: node ${e.source}`);
    }
  }

  // Disconnected nodes warning
  if (nodes.length > 1) {
    const connectedIds = new Set<string>();
    for (const e of edges) {
      connectedIds.add(e.source);
      connectedIds.add(e.target);
    }
    for (const n of nodes) {
      if (!connectedIds.has(n.id)) {
        const name = (n.data as Record<string, unknown>)?.name ?? n.id;
        warnings.push(`Node ${name} is disconnected`);
      }
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}
