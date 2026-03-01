import { create } from 'zustand';
import { SimulationStatus, type SimulationResult } from '../types';
import { useFlowsheetStore } from './flowsheetStore';
import { runSimulation as apiRunSimulation } from '../lib/api-client';

interface SimulationState {
  status: SimulationStatus;
  results: SimulationResult | null;
  error: string | null;
  propertyPackage: string;
  abortController: AbortController | null;

  runSimulation: () => Promise<void>;
  cancelSimulation: () => void;
  setStatus: (status: SimulationStatus) => void;
  setResults: (results: SimulationResult | null) => void;
  setPropertyPackage: (pkg: string) => void;
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  status: SimulationStatus.Idle,
  results: null,
  error: null,
  propertyPackage: 'PengRobinson',
  abortController: null,

  runSimulation: async () => {
    // Abort any previous in-flight simulation
    get().abortController?.abort();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    set({ status: SimulationStatus.Running, error: null, abortController: controller });

    const { nodes, edges } = useFlowsheetStore.getState();

    if (nodes.length === 0) {
      set({
        status: SimulationStatus.Error,
        error: 'No equipment on the flowsheet. Add at least one equipment node before running the simulation.',
      });
      return;
    }

    // Validate feed compositions (B4)
    const feedNodeIds = new Set(nodes.map((n) => n.id));
    for (const e of edges) {
      feedNodeIds.delete(e.target);
    }
    const warnings: string[] = [];
    const simNodes = nodes.map((n) => {
      const params = { ...n.data.parameters };
      if (feedNodeIds.has(n.id) && params.feedComposition) {
        try {
          const comp: Record<string, number> =
            typeof params.feedComposition === 'string'
              ? JSON.parse(params.feedComposition as string)
              : (params.feedComposition as unknown as Record<string, number>);
          const entries = Object.entries(comp).filter(([, v]) => typeof v === 'number');
          if (entries.length === 0) {
            warnings.push(`${n.data.name}: empty feed composition — using defaults`);
          } else {
            const total = entries.reduce((s, [, v]) => s + v, 0);
            if (total > 0 && (total < 0.95 || total > 1.05)) {
              const normalized = Object.fromEntries(entries.map(([k, v]) => [k, v / total]));
              params.feedComposition = JSON.stringify(normalized);
              warnings.push(`${n.data.name}: feed composition auto-normalized (was ${total.toFixed(3)})`);
            }
          }
        } catch {
          // Not valid JSON — leave as-is
        }
      }
      return {
        id: n.id,
        type: n.data.equipmentType,
        name: n.data.name,
        parameters: params,
        position: n.position,
      };
    });

    const simEdges = edges.map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? '',
      target: e.target,
      targetHandle: e.targetHandle ?? '',
    }));

    const { propertyPackage } = useSimulationStore.getState();

    try {
      const data = await apiRunSimulation({ nodes: simNodes, edges: simEdges, property_package: propertyPackage }, controller.signal);
      clearTimeout(timeout);
      if (data.status === 'error') {
        set({
          status: SimulationStatus.Error,
          error: data.error ?? 'Simulation failed',
        });
      } else {
        const result: SimulationResult = {
          streamResults: (data.results?.stream_results as Record<string, SimulationResult['streamResults'][string]>) ?? {},
          equipmentResults: (data.results?.equipment_results as Record<string, Record<string, number | string>>) ?? {},
          convergenceInfo: {
            iterations: (data.results?.convergence_info as Record<string, number>)?.iterations ?? 0,
            converged: (data.results?.convergence_info as Record<string, boolean>)?.converged ?? false,
            error: (data.results?.convergence_info as Record<string, number>)?.error ?? 0,
          },
          logs: [...warnings.map((w) => `WARNING: ${w}`), ...((data.results?.logs as string[]) ?? [])],
        };
        set({ status: SimulationStatus.Completed, results: result, abortController: null });
      }
    } catch (err) {
      clearTimeout(timeout);
      if (err instanceof DOMException && err.name === 'AbortError') {
        set({
          status: SimulationStatus.Error,
          error: 'Simulation cancelled or timed out (60s limit)',
          abortController: null,
        });
      } else {
        set({
          status: SimulationStatus.Error,
          error: err instanceof Error ? err.message : 'Unknown error occurred',
          abortController: null,
        });
      }
    }
  },

  cancelSimulation: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
      set({ abortController: null });
    }
  },

  setStatus: (status) => set({ status }),
  setResults: (results) => set({ results }),
  setPropertyPackage: (pkg) => set({ propertyPackage: pkg }),
}));
