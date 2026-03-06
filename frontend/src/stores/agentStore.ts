import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';
import { toast } from 'sonner';
import { EquipmentType, type AgentMessage, type EquipmentData } from '../types';
import { agentChat, getChatHistory, saveChatMessages, clearChatHistory, type FlowsheetActionData } from '../lib/api-client';
import { getDefaultParameters, equipmentLibrary } from '../lib/equipment-library';
import { autoLayout } from '../lib/auto-layout';
import { useFlowsheetStore } from './flowsheetStore';
import { useSimulationStore } from './simulationStore';

interface AgentState {
  messages: AgentMessage[];
  isOpen: boolean;
  isLoading: boolean;

  sendMessage: (content: string) => Promise<void>;
  togglePanel: () => void;
  addMessage: (role: AgentMessage['role'], content: string) => void;
  setLoading: (loading: boolean) => void;
  clearMessages: () => void;
  loadChatHistory: (projectId: string) => Promise<void>;
}

const VALID_TYPES = new Set<string>(Object.values(EquipmentType));

function applyFlowsheetAction(action: FlowsheetActionData): void {
  // Filter out invalid equipment types
  const validEquipment = action.equipment.filter((eq) => {
    if (!VALID_TYPES.has(eq.type)) {
      console.warn(`Skipping unknown equipment type from AI: ${eq.type}`);
      return false;
    }
    return true;
  });

  // Map temp IDs → real UUIDs
  const idMap = new Map<string, string>();
  for (const eq of validEquipment) {
    idMap.set(eq.id, uuidv4());
  }

  // Filter connections to only reference valid equipment
  const validIds = new Set(validEquipment.map((eq) => eq.id));
  const validConnections = action.connections.filter(
    (c) => validIds.has(c.source_id) && validIds.has(c.target_id)
  );

  // Compute positions via auto-layout
  const positions = autoLayout(
    validEquipment.map((eq) => eq.id),
    validConnections,
  );
  const posMap = new Map(positions.map((p) => [p.id, { x: p.x, y: p.y }]));

  // Build equipment array
  const equipment: EquipmentData[] = validEquipment.map((eq) => {
    const eqType = eq.type as EquipmentType;
    const defaults = getDefaultParameters(eqType);
    const params = { ...defaults };

    // Merge AI-specified parameters over defaults
    if (eq.parameters) {
      for (const [key, value] of Object.entries(eq.parameters)) {
        if (key === 'feedComposition' && typeof value === 'object' && value !== null) {
          // Stringify if AI sent object instead of string
          params[key] = JSON.stringify(value);
        } else {
          params[key] = value as number | string | boolean;
        }
      }
    }

    return {
      id: idMap.get(eq.id)!,
      type: eqType,
      name: eq.name,
      parameters: params,
      position: posMap.get(eq.id) ?? { x: 100, y: 100 },
    };
  });

  // Build streams array
  const streams = validConnections.map((conn) => ({
    id: uuidv4(),
    sourceId: idMap.get(conn.source_id) ?? conn.source_id,
    sourcePort: conn.source_port,
    targetId: idMap.get(conn.target_id) ?? conn.target_id,
    targetPort: conn.target_port,
  }));

  // Auto-create ProductStream for any REQUIRED equipment outlet port with no outgoing connection
  // Skip ports explicitly marked as optional (e.g., DistillationColumn side draws)
  const connectedPorts = new Set(streams.map(s => `${s.sourceId}:${s.sourcePort}`));
  for (const eq of [...equipment]) {
    const def = equipmentLibrary[eq.type];
    if (!def) continue;
    for (const port of def.ports) {
      if (port.type === 'outlet' && !port.id.startsWith('energy-') && port.required !== false && !connectedPorts.has(`${eq.id}:${port.id}`)) {
        const prodId = uuidv4();
        equipment.push({
          id: prodId,
          type: EquipmentType.ProductStream,
          name: 'Product',
          parameters: {},
          position: { x: (eq.position?.x ?? 100) + 200, y: (eq.position?.y ?? 100) },
        });
        streams.push({
          id: uuidv4(),
          sourceId: eq.id,
          sourcePort: port.id,
          targetId: prodId,
          targetPort: 'in-1',
        });
      }
    }
  }

  if (action.mode === 'add') {
    // Merge: append new nodes/edges to existing state
    const store = useFlowsheetStore.getState();
    const existingNodes = store.nodes;
    const existingEdges = store.edges;

    // Offset new nodes to avoid overlap with existing ones
    const maxX = existingNodes.reduce((m, n) => Math.max(m, n.position.x), 0);
    const offsetX = maxX > 0 ? maxX + 250 : 0;

    const offsetEquipment = equipment.map((eq) => ({
      ...eq,
      position: { x: eq.position.x + offsetX, y: eq.position.y },
    }));

    store.loadFlowsheet(
      [
        ...existingNodes.map((n) => ({
          id: n.id,
          type: n.data.equipmentType,
          name: n.data.name,
          parameters: n.data.parameters,
          position: n.position,
        })),
        ...offsetEquipment,
      ],
      [
        ...existingEdges.map((e) => ({
          id: e.id,
          sourceId: e.source,
          sourcePort: e.sourceHandle ?? '',
          targetId: e.target,
          targetPort: e.targetHandle ?? '',
        })),
        ...streams,
      ],
    );
  } else {
    // Replace: atomic swap via loadFlowsheet
    useFlowsheetStore.getState().loadFlowsheet(equipment, streams);
  }
}

export const useAgentStore = create<AgentState>((set, get) => ({
  messages: [
    {
      id: uuidv4(),
      role: 'system',
      content: 'Welcome to ProSim Cloud AI Assistant. I can help you build and optimize your process flowsheet. Try asking me to build a flowsheet or configure your simulation.',
      timestamp: new Date(),
    },
  ],
  isOpen: false,
  isLoading: false,

  sendMessage: async (content) => {
    const userMessage: AgentMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    set((state) => ({
      messages: [...state.messages, userMessage],
      isLoading: true,
    }));

    try {
      const chatMessages = get().messages
        .filter((m) => m.role !== 'system')
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      // Build compact flowsheet context for the AI
      const { nodes: fsNodes, edges: fsEdges } = useFlowsheetStore.getState();
      const { results: simResults, propertyPackage } = useSimulationStore.getState();
      const flowsheetContext: Record<string, unknown> = {};
      if (fsNodes.length > 0) {
        flowsheetContext.equipment = fsNodes.map((n) => ({
          id: n.id,
          type: n.data?.equipmentType,
          name: n.data?.name,
          parameters: n.data?.parameters,
        }));
        flowsheetContext.connections = fsEdges.map((e) => ({
          source: e.source,
          sourceHandle: e.sourceHandle,
          target: e.target,
          targetHandle: e.targetHandle,
        }));
        flowsheetContext.propertyPackage = propertyPackage;
        if (simResults) {
          flowsheetContext.simulationResults = {
            streams: simResults.streamResults,
            equipment: simResults.equipmentResults,
            converged: simResults.convergenceInfo?.converged,
            iterations: simResults.convergenceInfo?.iterations,
            logs: simResults.logs?.filter(
              (l) => l.startsWith('WARNING') || l.startsWith('ERROR')
            ).slice(0, 20),
          };
        }
      }

      const data = await agentChat(
        chatMessages,
        Object.keys(flowsheetContext).length > 0 ? flowsheetContext : undefined,
      );

      // Apply flowsheet action if present
      let flowsheetAction: AgentMessage['flowsheetAction'] | undefined;
      if (data.flowsheet_action) {
        try {
          applyFlowsheetAction(data.flowsheet_action);
          flowsheetAction = {
            equipmentCount: data.flowsheet_action.equipment.length,
            connectionCount: data.flowsheet_action.connections.length,
          };
          const fixCount = data.completion_log?.length ?? 0;
          const fixSuffix = fixCount > 0 ? ` (${fixCount} auto-fixed)` : '';
          toast.success(`Created ${flowsheetAction.equipmentCount} equipment with ${flowsheetAction.connectionCount} connections${fixSuffix}`);
          // Auto-simulate after AI generates a flowsheet
          setTimeout(() => {
            useSimulationStore.getState().runSimulation().catch((err) => {
              console.error('Auto-simulation after AI flowsheet failed:', err);
            });
          }, 100);
        } catch (e) {
          console.error('Failed to apply flowsheet action:', e);
        }
      }

      const assistantMessage: AgentMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: data.message?.content ?? 'No response received.',
        timestamp: new Date(),
        flowsheetAction,
      };
      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
      }));

      // Persist new messages to backend
      const projectId = useFlowsheetStore.getState().currentProjectId;
      if (projectId) {
        saveChatMessages(projectId, [
          { role: 'user', content },
          { role: 'assistant', content: assistantMessage.content },
        ]).catch((err) => console.error('Failed to save chat messages:', err));
      }
    } catch {
      const errorMessage: AgentMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: 'Sorry, I was unable to connect to the AI service. Please check that the backend is running.',
        timestamp: new Date(),
      };
      set((state) => ({
        messages: [...state.messages, errorMessage],
        isLoading: false,
      }));
    }
  },

  togglePanel: () => {
    set((state) => ({ isOpen: !state.isOpen }));
  },

  addMessage: (role, content) => {
    const message: AgentMessage = {
      id: uuidv4(),
      role,
      content,
      timestamp: new Date(),
    };
    set((state) => ({ messages: [...state.messages, message] }));
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },

  clearMessages: () => {
    set({
      messages: [
        {
          id: uuidv4(),
          role: 'system',
          content: 'Welcome to ProSim Cloud AI Assistant. I can help you build and optimize your process flowsheet. Try asking me to build a flowsheet or configure your simulation.',
          timestamp: new Date(),
        },
      ],
    });
    const projectId = useFlowsheetStore.getState().currentProjectId;
    if (projectId) {
      clearChatHistory(projectId).catch((err) =>
        console.error('Failed to clear chat history:', err)
      );
    }
  },

  loadChatHistory: async (projectId: string) => {
    try {
      const data = await getChatHistory(projectId);
      if (data.messages.length > 0) {
        const loaded: AgentMessage[] = [
          {
            id: uuidv4(),
            role: 'system',
            content: 'Welcome to ProSim Cloud AI Assistant. I can help you build and optimize your process flowsheet. Try asking me to build a flowsheet or configure your simulation.',
            timestamp: new Date(),
          },
          ...data.messages.map((m) => ({
            id: m.id,
            role: m.role as AgentMessage['role'],
            content: m.content,
            timestamp: new Date(m.created_at),
          })),
        ];
        set({ messages: loaded });
      }
    } catch {
      // Chat history not available, keep default welcome message
    }
  },
}));
