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
import {
  listProjects,
  createProject,
  getFlowsheet,
  saveFlowsheet,
  updateProject,
} from '../lib/api-client';

export interface EquipmentNodeData extends Record<string, unknown> {
  equipmentType: EquipmentType;
  name: string;
  parameters: Record<string, number | string | boolean>;
}

interface FlowsheetState {
  nodes: Node<EquipmentNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  currentProjectId: string | null;
  projectName: string;

  addNode: (type: EquipmentType, position: { x: number; y: number }) => void;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, data: Partial<EquipmentNodeData>) => void;
  onNodesChange: OnNodesChange<Node<EquipmentNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  setSelectedNode: (id: string | null) => void;
  loadFlowsheet: (equipment: EquipmentData[], streams: { id: string; sourceId: string; sourcePort: string; targetId: string; targetPort: string }[]) => void;
  getUpstreamNodes: (nodeId: string) => string[];
  clear: () => void;
  setProjectName: (name: string) => void;
  initProject: () => Promise<void>;
}

let saveTimeout: ReturnType<typeof setTimeout> | null = null;
function debounceSave(get: () => FlowsheetState) {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(() => {
    const { currentProjectId, nodes, edges } = get();
    if (currentProjectId) {
      saveFlowsheet(currentProjectId, nodes as any, edges as any).catch(() => {});
    }
  }, 1000);
}

export const useFlowsheetStore = create<FlowsheetState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  currentProjectId: null,
  projectName: 'Untitled Project',

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
    debounceSave(get);
  },

  removeNode: (id) => {
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
    }));
    debounceSave(get);
  },

  updateNodeData: (id, data) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id
          ? { ...node, data: { ...node.data, ...data } }
          : node
      ),
    }));
    debounceSave(get);
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
    debounceSave(get);
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
    debounceSave(get);
  },

  getUpstreamNodes: (nodeId: string) => {
    return get().edges.filter((e) => e.target === nodeId).map((e) => e.source);
  },

  clear: () => {
    set({ nodes: [], edges: [], selectedNodeId: null });
  },

  setProjectName: (name) => {
    set({ projectName: name });
    const { currentProjectId } = get();
    if (currentProjectId) {
      updateProject(currentProjectId, { name }).catch(() => {});
    }
  },

  initProject: async () => {
    try {
      const projects = await listProjects();
      if (projects.length > 0) {
        const project = projects[0];
        set({ currentProjectId: project.id, projectName: project.name });
        try {
          const flowsheet = await getFlowsheet(project.id);
          if (flowsheet.nodes && flowsheet.nodes.length > 0) {
            const equipment: EquipmentData[] = flowsheet.nodes.map((n: any) => ({
              id: n.id,
              type: n.data?.equipmentType ?? n.type,
              name: n.data?.name ?? n.name ?? '',
              parameters: n.data?.parameters ?? n.parameters ?? {},
              position: n.position ?? { x: 0, y: 0 },
            }));
            const streams = (flowsheet.edges ?? []).map((e: any) => ({
              id: e.id,
              sourceId: e.source,
              sourcePort: e.sourceHandle ?? e.source_handle ?? '',
              targetId: e.target,
              targetPort: e.targetHandle ?? e.target_handle ?? '',
            }));
            get().loadFlowsheet(equipment, streams);
          }
        } catch {
          // No flowsheet saved yet, that's fine
        }
      } else {
        const project = await createProject('Untitled Project');
        set({ currentProjectId: project.id, projectName: project.name });
      }
    } catch {
      // API not available, continue with local-only mode
    }
  },
}));
