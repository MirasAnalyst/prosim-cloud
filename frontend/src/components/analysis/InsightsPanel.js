import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { X, Loader2, Sparkles, Upload } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import EconomicParamsForm, { DEFAULT_ECONOMIC_PARAMS } from './EconomicParamsForm';
import InsightsResultsView from './InsightsResultsView';
export default function InsightsPanel({ open, onClose }) {
    const simResults = useSimulationStore((s) => s.results);
    const nodes = useFlowsheetStore((s) => s.nodes);
    const edges = useFlowsheetStore((s) => s.edges);
    const propertyPackage = useFlowsheetStore((s) => s.simulationBasis?.property_package ?? 'PengRobinson');
    const [econParams, setEconParams] = useState({ ...DEFAULT_ECONOMIC_PARAMS });
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const run = async () => {
        if (!simResults)
            return;
        setRunning(true);
        setError('');
        setResults(null);
        try {
            const res = await fetch('/api/simulation/insights', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    simulation_results: {
                        stream_results: simResults.streamResults,
                        equipment_results: simResults.equipmentResults,
                        convergence_info: simResults.convergenceInfo,
                    },
                    nodes: nodes.map((n) => ({
                        id: n.id,
                        type: n.data?.equipmentType ?? n.type,
                        name: n.data?.name ?? n.id,
                        parameters: n.data?.parameters ?? {},
                    })),
                    edges: edges.map((e) => ({
                        id: e.id,
                        source: e.source,
                        sourceHandle: e.sourceHandle ?? '',
                        target: e.target,
                        targetHandle: e.targetHandle ?? '',
                        type: e.type ?? 'stream',
                    })),
                    property_package: propertyPackage,
                    economic_params: {
                        steam_cost: econParams.steamCost,
                        cooling_water_cost: econParams.cwCost,
                        electricity_cost: econParams.elecCost,
                        fuel_gas_cost: econParams.fuelCost,
                        carbon_price: econParams.carbonPrice,
                        hours_per_year: econParams.hoursPerYear,
                    },
                }),
            });
            const data = await res.json();
            if (data.status === 'error') {
                setError(data.error || 'Analysis failed');
            }
            else {
                setResults(data);
            }
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed');
        }
        finally {
            setRunning(false);
        }
    };
    if (!open)
        return null;
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(Sparkles, { size: 16, className: "text-amber-500" }), _jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Optimization Insights" })] }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsx(EconomicParamsForm, { value: econParams, onChange: setEconParams }), _jsxs("button", { onClick: run, disabled: running || !simResults, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-amber-600 text-white rounded text-sm font-medium hover:bg-amber-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Sparkles, { size: 14 }), running ? 'Analyzing...' : 'Analyze with AI'] }), !simResults && (_jsx("div", { className: "text-xs text-yellow-500", children: "Run a simulation first to generate insights." })), error && _jsx("div", { className: "text-xs text-red-400", children: error }), _jsxs(Link, { to: "/app/insights", className: "flex items-center gap-1.5 text-xs text-blue-500 hover:text-blue-400 transition-colors", children: [_jsx(Upload, { size: 12 }), "Or upload simulation results from another tool"] }), results && results.status === 'success' && (_jsx(InsightsResultsView, { results: results }))] })] }));
}
