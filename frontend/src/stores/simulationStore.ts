import { create } from 'zustand';
import { SimulationStatus, type SimulationResult } from '../types';
import { useFlowsheetStore } from './flowsheetStore';
import { runSimulation as apiRunSimulation } from '../lib/api-client';

interface SimulationState {
  status: SimulationStatus;
  results: SimulationResult | null;
  error: string | null;

  runSimulation: () => Promise<void>;
  setStatus: (status: SimulationStatus) => void;
  setResults: (results: SimulationResult | null) => void;
}

export const useSimulationStore = create<SimulationState>((set) => ({
  status: SimulationStatus.Idle,
  results: null,
  error: null,

  runSimulation: async () => {
    set({ status: SimulationStatus.Running, error: null });

    const { nodes, edges } = useFlowsheetStore.getState();

    const simNodes = nodes.map((n) => ({
      id: n.id,
      type: n.data.equipmentType,
      name: n.data.name,
      parameters: n.data.parameters,
      position: n.position,
    }));

    const simEdges = edges.map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? '',
      target: e.target,
      targetHandle: e.targetHandle ?? '',
    }));

    try {
      const data = await apiRunSimulation({ nodes: simNodes, edges: simEdges });
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
          logs: (data.results?.logs as string[]) ?? [],
        };
        set({ status: SimulationStatus.Completed, results: result });
      }
    } catch (err) {
      set({
        status: SimulationStatus.Error,
        error: err instanceof Error ? err.message : 'Unknown error occurred',
      });
    }
  },

  setStatus: (status) => set({ status }),
  setResults: (results) => set({ results }),
}));
