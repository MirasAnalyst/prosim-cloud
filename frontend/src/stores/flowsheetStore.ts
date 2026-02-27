import { create } from 'zustand';
import {
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
} from '@xyflow/react';
import { v4 as uuidv4 } from 'uuid';
import { EquipmentType, type EquipmentData } from '../types';
import { equipmentLibrary, getDefaultParameters } from '../lib/equipment-library';

export interface EquipmentNodeData extends Record<string, unknown> {
  equipmentType: EquipmentType;
  name: string;
  parameters: Record<string, number | string | boolean>;
}

interface FlowsheetState {
  nodes: Node<EquipmentNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;

  addNode: (type: EquipmentType, position: { x: number; y: number }) => void;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, data: Partial<EquipmentNodeData>) => void;
  onNodesChange: OnNodesChange<Node<EquipmentNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  setSelectedNode: (id: string | null) => void;
  loadFlowsheet: (equipment: EquipmentData[], streams: { id: string; sourceId: string; sourcePort: string; targetId: string; targetPort: string }[]) => void;
  clear: () => void;
}

export const useFlowsheetStore = create<FlowsheetState>((set) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,

  addNode: (type, position) => {
    const def = equipmentLibrary[type];
    const id = uuidv4();
    const newNode: Node<EquipmentNodeData> = {
      id,
      type: 'equipment',
      position,
      data: {
        equipmentType: type,
        name: def.label,
        parameters: getDefaultParameters(type),
      },
    };
    set((state) => ({ nodes: [...state.nodes, newNode] }));
  },

  removeNode: (id) => {
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
    }));
  },

  updateNodeData: (id, data) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id
          ? { ...node, data: { ...node.data, ...data } }
          : node
      ),
    }));
  },

  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    }));
    const selectChange = changes.find((c) => c.type === 'select');
    if (selectChange && selectChange.type === 'select') {
      set({ selectedNodeId: selectChange.selected ? selectChange.id : null });
    }
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
    }));
  },

  onConnect: (connection) => {
    set((state) => ({
      edges: addEdge(
        {
          ...connection,
          type: 'stream',
          animated: true,
        },
        state.edges
      ),
    }));
  },

  setSelectedNode: (id) => {
    set({ selectedNodeId: id });
  },

  loadFlowsheet: (equipment, streams) => {
    const nodes: Node<EquipmentNodeData>[] = equipment.map((eq) => ({
      id: eq.id,
      type: 'equipment',
      position: eq.position,
      data: {
        equipmentType: eq.type,
        name: eq.name,
        parameters: eq.parameters,
      },
    }));
    const edges: Edge[] = streams.map((s) => ({
      id: s.id,
      source: s.sourceId,
      sourceHandle: s.sourcePort,
      target: s.targetId,
      targetHandle: s.targetPort,
      type: 'stream',
      animated: true,
    }));
    set({ nodes, edges, selectedNodeId: null });
  },

  clear: () => {
    set({ nodes: [], edges: [], selectedNodeId: null });
  },
}));
