import { create } from 'zustand';
import { toast } from 'sonner';
import { SimulationStatus } from '../types';
import { useFlowsheetStore } from './flowsheetStore';
import { validateFlowsheet } from '../lib/flowsheet-validator';
export const useSimulationStore = create((set, get) => ({
    status: SimulationStatus.Idle,
    results: null,
    error: null,
    propertyPackage: 'PengRobinson',
    abortController: null,
    convergenceSettings: { maxIter: 50, tolerance: 0.0001, damping: 0.5 },
    progress: null,
    batchResults: null,
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
        // Client-side validation
        const validation = validateFlowsheet(nodes, edges);
        if (!validation.valid) {
            for (const err of validation.errors)
                toast.error(err);
            set({
                status: SimulationStatus.Error,
                error: `Validation failed: ${validation.errors.join('; ')}`,
                abortController: null,
            });
            return;
        }
        for (const w of validation.warnings)
            toast.warning(w);
        // Validate feed compositions (B4)
        const feedNodeIds = new Set(nodes.map((n) => n.id));
        for (const e of edges) {
            feedNodeIds.delete(e.target);
        }
        const warnings = [];
        const simNodes = nodes.map((n) => {
            const params = { ...n.data.parameters };
            if (feedNodeIds.has(n.id) && params.feedComposition) {
                try {
                    const comp = typeof params.feedComposition === 'string'
                        ? JSON.parse(params.feedComposition)
                        : params.feedComposition;
                    const entries = Object.entries(comp).filter(([, v]) => typeof v === 'number');
                    if (entries.length === 0) {
                        warnings.push(`${n.data.name}: empty feed composition — using defaults`);
                    }
                    else {
                        const total = entries.reduce((s, [, v]) => s + v, 0);
                        if (total > 0 && (total < 0.95 || total > 1.05)) {
                            const normalized = Object.fromEntries(entries.map(([k, v]) => [k, v / total]));
                            params.feedComposition = JSON.stringify(normalized);
                            warnings.push(`${n.data.name}: feed composition auto-normalized (was ${total.toFixed(3)})`);
                        }
                    }
                }
                catch {
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
        const { propertyPackage, convergenceSettings } = useSimulationStore.getState();
        const { simulationBasis } = useFlowsheetStore.getState();
        try {
            const response = await fetch('/api/simulation/run/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nodes: simNodes,
                    edges: simEdges,
                    property_package: propertyPackage,
                    convergence_settings: {
                        max_iter: convergenceSettings.maxIter,
                        tolerance: convergenceSettings.tolerance,
                        damping: convergenceSettings.damping,
                    },
                    simulation_basis: simulationBasis.compounds.length > 0 ? simulationBasis : undefined,
                }),
                signal: controller.signal,
            });
            clearTimeout(timeout);
            if (!response.ok || !response.body) {
                const text = await response.text();
                set({ status: SimulationStatus.Error, error: text || 'Simulation request failed', abortController: null });
                toast.error('Simulation request failed');
                return;
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let data = null;
            while (true) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop() ?? '';
                for (const part of parts) {
                    let eventType = '';
                    let eventData = '';
                    for (const line of part.split('\n')) {
                        if (line.startsWith('event: '))
                            eventType = line.slice(7).trim();
                        else if (line.startsWith('data: '))
                            eventData = line.slice(6);
                    }
                    if (!eventType || !eventData)
                        continue;
                    if (eventType === 'progress') {
                        try {
                            const prog = JSON.parse(eventData);
                            set({ progress: { equipment: prog.equipment, index: prog.index, total: prog.total } });
                        }
                        catch { /* skip malformed progress */ }
                    }
                    else if (eventType === 'complete') {
                        try {
                            data = JSON.parse(eventData);
                        }
                        catch { /* skip malformed complete */ }
                    }
                }
            }
            set({ progress: null });
            if (!data) {
                set({ status: SimulationStatus.Error, error: 'No simulation result received', abortController: null });
                toast.error('No simulation result received');
                return;
            }
            // SSE complete event sends the raw engine result (flat structure),
            // unlike the POST endpoint which wraps it in {results: ...}
            const res = data.results ?? data;
            if ((data.status ?? res.status) === 'error') {
                set({
                    status: SimulationStatus.Error,
                    error: data.error ?? res.error ?? 'Simulation failed',
                });
                toast.error(data.error ?? res.error ?? 'Simulation failed');
            }
            else {
                const result = {
                    streamResults: res.stream_results ?? {},
                    equipmentResults: res.equipment_results ?? {},
                    convergenceInfo: {
                        iterations: res.convergence_info?.iterations ?? 0,
                        converged: res.convergence_info?.converged ?? false,
                        error: res.convergence_info?.error ?? 0,
                    },
                    logs: [...warnings.map((w) => `WARNING: ${w}`), ...(res.logs ?? [])],
                };
                set({ status: SimulationStatus.Completed, results: result, abortController: null });
                toast.success('Simulation completed');
            }
        }
        catch (err) {
            clearTimeout(timeout);
            set({ progress: null });
            if (err instanceof DOMException && err.name === 'AbortError') {
                set({
                    status: SimulationStatus.Error,
                    error: 'Simulation cancelled or timed out (60s limit)',
                    abortController: null,
                });
                toast.error('Simulation cancelled or timed out (60s limit)');
            }
            else {
                set({
                    status: SimulationStatus.Error,
                    error: err instanceof Error ? err.message : 'Unknown error occurred',
                    abortController: null,
                });
                toast.error(err instanceof Error ? err.message : 'Unknown error occurred');
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
    setConvergenceSettings: (settings) => set((state) => ({
        convergenceSettings: { ...state.convergenceSettings, ...settings },
    })),
    runBatchSimulation: async (variations) => {
        set({ status: SimulationStatus.Running, error: null, batchResults: null });
        const { nodes, edges } = useFlowsheetStore.getState();
        const { propertyPackage, convergenceSettings } = get();
        const simNodes = nodes.map((n) => ({
            id: n.id,
            type: n.data.equipmentType,
            name: n.data.name,
            parameters: { ...n.data.parameters },
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
            const res = await fetch('/api/simulation/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_nodes: simNodes,
                    base_edges: simEdges,
                    property_package: propertyPackage,
                    convergence_settings: {
                        max_iter: convergenceSettings.maxIter,
                        tolerance: convergenceSettings.tolerance,
                        damping: convergenceSettings.damping,
                    },
                    variations: variations.map((v) => ({
                        node_id: v.nodeId,
                        parameter_key: v.parameterKey,
                        values: v.values,
                    })),
                }),
            });
            const data = await res.json();
            set({
                status: SimulationStatus.Completed,
                batchResults: { results: data.results, parameterMatrix: data.parameter_matrix },
            });
            toast.success(`Batch simulation complete: ${data.results?.length ?? 0} runs`);
        }
        catch (err) {
            set({
                status: SimulationStatus.Error,
                error: err instanceof Error ? err.message : 'Batch simulation failed',
            });
            toast.error('Batch simulation failed');
        }
    },
}));
