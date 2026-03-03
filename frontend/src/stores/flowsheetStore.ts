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

export interface EquipmentGroup {
  id: string;
  label: string;
  nodeIds: string[];
  collapsed: boolean;
  position: { x: number; y: number };
  size: { width: number; height: number };
}

export interface SimulationBasis {
  compounds: string[];
  property_package?: string;
  bip_overrides?: Record<string, number>;
}

interface FlowsheetState {
  nodes: Node<EquipmentNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  currentProjectId: string | null;
  projectName: string;
  saveStatus: 'saved' | 'saving' | 'error';
  simulationBasis: SimulationBasis;

  // Equipment Groups
  groups: EquipmentGroup[];
  createGroup: (label: string, nodeIds: string[]) => void;
  removeGroup: (id: string) => void;
  toggleGroupCollapse: (id: string) => void;

  // Undo/Redo
  history: Array<{ nodes: Node<EquipmentNodeData>[]; edges: Edge[] }>;
  historyIndex: number;
  _isRestoring: boolean;
  pushHistory: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // Copy/Paste
  clipboard: { nodes: Node<EquipmentNodeData>[]; edges: Edge[] } | null;
  copySelected: () => void;
  pasteClipboard: () => void;

  addNode: (type: EquipmentType, position: { x: number; y: number }) => void;
  removeNode: (id: string) => void;
  updateNodeData: (id: string, data: Partial<EquipmentNodeData>) => void;
  onNodesChange: OnNodesChange<Node<EquipmentNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  setSelectedNode: (id: string | null) => void;
  setSelectedEdge: (id: string | null) => void;
  loadFlowsheet: (equipment: EquipmentData[], streams: { id: string; sourceId: string; sourcePort: string; targetId: string; targetPort: string }[]) => void;
  getUpstreamNodes: (nodeId: string) => string[];
  clear: () => void;
  setProjectName: (name: string) => void;
  setSimulationBasis: (basis: SimulationBasis) => void;
  initProject: () => Promise<void>;
}

let saveTimeout: ReturnType<typeof setTimeout> | null = null;
function debounceSave(get: () => FlowsheetState, set?: (partial: Partial<FlowsheetState>) => void) {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(() => {
    const { currentProjectId, nodes, edges, simulationBasis } = get();
    if (currentProjectId) {
      set?.({ saveStatus: 'saving' });
      saveFlowsheet(currentProjectId, nodes as any, edges as any, simulationBasis)
        .then(() => set?.({ saveStatus: 'saved' }))
        .catch(() => set?.({ saveStatus: 'error' }));
    }
  }, 1000);
}

export const useFlowsheetStore = create<FlowsheetState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  selectedEdgeId: null,
  currentProjectId: null,
  projectName: 'Untitled Project',
  saveStatus: 'saved' as const,
  simulationBasis: { compounds: [] },

  // Equipment Groups
  groups: [],

  createGroup: (label, nodeIds) => {
    const { nodes } = get();
    const groupNodes = nodes.filter(n => nodeIds.includes(n.id));
    if (groupNodes.length < 2) return;

    const minX = Math.min(...groupNodes.map(n => n.position.x)) - 20;
    const minY = Math.min(...groupNodes.map(n => n.position.y)) - 40;
    const maxX = Math.max(...groupNodes.map(n => n.position.x)) + 200;
    const maxY = Math.max(...groupNodes.map(n => n.position.y)) + 120;

    set(state => ({
      groups: [...state.groups, {
        id: crypto.randomUUID(),
        label,
        nodeIds,
        collapsed: false,
        position: { x: minX, y: minY },
        size: { width: maxX - minX, height: maxY - minY },
      }],
    }));
  },

  removeGroup: (id) => {
    set(state => ({ groups: state.groups.filter(g => g.id !== id) }));
  },

  toggleGroupCollapse: (id) => {
    set(state => ({
      groups: state.groups.map(g => g.id === id ? { ...g, collapsed: !g.collapsed } : g),
    }));
  },

  // Undo/Redo state
  history: [],
  historyIndex: -1,
  _isRestoring: false,

  pushHistory: () => {
    if (get()._isRestoring) return;
    const { nodes, edges, history, historyIndex } = get();
    const snapshot = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(snapshot);
    // Cap at 50 entries
    if (newHistory.length > 50) {
      newHistory.shift();
      set({ history: newHistory, historyIndex: newHistory.length - 1 });
    } else {
      set({ history: newHistory, historyIndex: newHistory.length - 1 });
    }
  },

  undo: () => {
    const { historyIndex, history } = get();
    if (historyIndex <= 0) return;
    const newIndex = historyIndex - 1;
    const snapshot = history[newIndex];
    set({ _isRestoring: true });
    set({
      nodes: JSON.parse(JSON.stringify(snapshot.nodes)),
      edges: JSON.parse(JSON.stringify(snapshot.edges)),
      historyIndex: newIndex,
    });
    set({ _isRestoring: false });
    debounceSave(get, set);
  },

  redo: () => {
    const { historyIndex, history } = get();
    if (historyIndex >= history.length - 1) return;
    const newIndex = historyIndex + 1;
    const snapshot = history[newIndex];
    set({ _isRestoring: true });
    set({
      nodes: JSON.parse(JSON.stringify(snapshot.nodes)),
      edges: JSON.parse(JSON.stringify(snapshot.edges)),
      historyIndex: newIndex,
    });
    set({ _isRestoring: false });
    debounceSave(get, set);
  },

  canUndo: () => get().historyIndex > 0,
  canRedo: () => get().historyIndex < get().history.length - 1,

  // Copy/Paste state
  clipboard: null,

  copySelected: () => {
    const { nodes, edges } = get();
    const selectedNodes = nodes.filter((n) => n.selected);
    if (selectedNodes.length === 0) return;
    const selectedIds = new Set(selectedNodes.map((n) => n.id));
    const selectedEdges = edges.filter(
      (e) => selectedIds.has(e.source) && selectedIds.has(e.target)
    );
    set({
      clipboard: {
        nodes: JSON.parse(JSON.stringify(selectedNodes)),
        edges: JSON.parse(JSON.stringify(selectedEdges)),
      },
    });
  },

  pasteClipboard: () => {
    const { clipboard } = get();
    if (!clipboard || clipboard.nodes.length === 0) return;
    const idMap = new Map<string, string>();
    clipboard.nodes.forEach((n) => {
      idMap.set(n.id, crypto.randomUUID());
    });
    const newNodes = clipboard.nodes.map((n) => ({
      ...JSON.parse(JSON.stringify(n)),
      id: idMap.get(n.id)!,
      position: { x: n.position.x + 40, y: n.position.y + 40 },
      selected: false,
    }));
    const newEdges = clipboard.edges.map((e) => ({
      ...JSON.parse(JSON.stringify(e)),
      id: crypto.randomUUID(),
      source: idMap.get(e.source) ?? e.source,
      target: idMap.get(e.target) ?? e.target,
    }));
    set((state) => ({
      nodes: [...state.nodes, ...newNodes],
      edges: [...state.edges, ...newEdges],
    }));
    get().pushHistory();
    debounceSave(get, set);
  },

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
    get().pushHistory();
    debounceSave(get, set);
  },

  removeNode: (id) => {
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
    }));
    get().pushHistory();
    debounceSave(get, set);
  },

  updateNodeData: (id, data) => {
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id
          ? { ...node, data: { ...node.data, ...data } }
          : node
      ),
    }));
    debounceSave(get, set);
  },

  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    }));
    const selectChange = changes.find((c) => c.type === 'select');
    if (selectChange && selectChange.type === 'select') {
      set({ selectedNodeId: selectChange.selected ? selectChange.id : null, selectedEdgeId: null });
    }
    // Push history for remove changes
    if (changes.some((c) => c.type === 'remove')) {
      get().pushHistory();
    }
    // Save position/dimension changes (not just selection)
    if (changes.some((c) => c.type === 'position' || c.type === 'dimensions' || c.type === 'remove')) {
      debounceSave(get, set);
    }
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
    }));
    const edgeSelect = changes.find((c) => c.type === 'select');
    if (edgeSelect && edgeSelect.type === 'select') {
      set({ selectedEdgeId: edgeSelect.selected ? edgeSelect.id : null, selectedNodeId: null });
    }
    if (changes.some((c) => c.type === 'remove')) {
      debounceSave(get, set);
    }
  },

  onConnect: (connection) => {
    // Detect energy port connections (handles starting with 'energy')
    const isEnergySource = connection.sourceHandle?.startsWith('energy') ?? false;
    const isEnergyTarget = connection.targetHandle?.startsWith('energy') ?? false;
    const edgeType = (isEnergySource || isEnergyTarget) ? 'energy-stream' : 'stream';

    set((state) => ({
      edges: addEdge(
        {
          ...connection,
          type: edgeType,
          animated: edgeType === 'stream',
        },
        state.edges
      ),
    }));
    get().pushHistory();
    debounceSave(get, set);
  },

  setSelectedNode: (id) => {
    set({ selectedNodeId: id, selectedEdgeId: id ? null : get().selectedEdgeId });
  },

  setSelectedEdge: (id) => {
    set({ selectedEdgeId: id, selectedNodeId: id ? null : get().selectedNodeId });
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
      type: (s as any).type ?? 'stream',
      animated: (s as any).type !== 'energy-stream',
    }));
    set({ nodes, edges, selectedNodeId: null, selectedEdgeId: null });
    get().pushHistory();
    debounceSave(get, set);
  },

  getUpstreamNodes: (nodeId: string) => {
    return get().edges.filter((e) => e.target === nodeId).map((e) => e.source);
  },

  clear: () => {
    set({ nodes: [], edges: [], selectedNodeId: null, selectedEdgeId: null });
  },

  setSimulationBasis: (basis) => {
    set({ simulationBasis: basis });
    debounceSave(get, set);
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
          // Load simulation basis if present
          if (flowsheet.simulation_basis) {
            const basis = flowsheet.simulation_basis as { compounds?: string[]; property_package?: string };
            set({
              simulationBasis: {
                compounds: basis.compounds ?? [],
                property_package: basis.property_package,
              },
            });
          }
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
              type: e.type ?? 'stream',
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

// Expose store on window for E2E testing
if (typeof window !== 'undefined') {
  (window as any).__ZUSTAND_FLOWSHEET_STORE__ = useFlowsheetStore;
}
