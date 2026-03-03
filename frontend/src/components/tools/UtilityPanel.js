import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
export default function UtilityPanel({ open, onClose }) {
    const simResults = useSimulationStore((s) => s.results);
    const [steamCost, setSteamCost] = useState(15.0);
    const [cwCost, setCwCost] = useState(3.0);
    const [elecCost, setElecCost] = useState(0.08);
    const [hoursPerYear, setHoursPerYear] = useState(8000);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const run = async () => {
        if (!simResults)
            return;
        setRunning(true);
        setError('');
        try {
            const raw = {
                stream_results: simResults.streamResults,
                equipment_results: simResults.equipmentResults,
            };
            const res = await fetch('/api/simulation/utility', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    simulation_results: raw,
                    costs: { steam_cost: steamCost, cooling_water_cost: cwCost, electricity_cost: elecCost },
                    hours_per_year: hoursPerYear,
                }),
            });
            const data = await res.json();
            if (data.error)
                setError(data.error);
            else
                setResults(data);
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Utility Summary" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Steam ($/GJ)" }), _jsx("input", { type: "number", value: steamCost, step: 0.5, onChange: (e) => setSteamCost(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "CW ($/GJ)" }), _jsx("input", { type: "number", value: cwCost, step: 0.5, onChange: (e) => setCwCost(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Electricity ($/kWh)" }), _jsx("input", { type: "number", value: elecCost, step: 0.01, onChange: (e) => setElecCost(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Hours/Year" }), _jsx("input", { type: "number", value: hoursPerYear, onChange: (e) => setHoursPerYear(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] }), _jsxs("button", { onClick: run, disabled: running || !simResults, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Computing...' : 'Compute Utilities'] }), !simResults && _jsx("div", { className: "text-xs text-yellow-500", children: "Run a simulation first to compute utility costs." }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && (_jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1", children: [_jsx("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: "Totals" }), _jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Heating: ", results.total_heating_kw, " kW"] }), _jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Cooling: ", results.total_cooling_kw, " kW"] }), _jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Power: ", results.total_power_kw, " kW"] }), _jsxs("div", { className: "text-xs font-semibold text-green-500 mt-1", children: ["Annual: $", results.total_annual_cost?.toLocaleString()] })] }), results.equipment_utilities?.length > 0 && (_jsxs("div", { children: [_jsx("div", { className: "text-xs font-medium text-gray-500 mb-1", children: "Equipment Breakdown" }), _jsxs("table", { className: "w-full text-xs", children: [_jsx("thead", { children: _jsxs("tr", { className: "text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700", children: [_jsx("th", { className: "text-left py-1", children: "Equipment" }), _jsx("th", { className: "text-left py-1", children: "Utility" }), _jsx("th", { className: "text-right py-1", children: "kW" }), _jsx("th", { className: "text-right py-1", children: "$/yr" })] }) }), _jsx("tbody", { children: results.equipment_utilities.map((eu, i) => (_jsxs("tr", { className: "text-gray-600 dark:text-gray-400 border-b border-gray-200/50 dark:border-gray-700/50", children: [_jsx("td", { className: "py-0.5 truncate max-w-[120px]", children: eu.equipment_name }), _jsx("td", { className: "py-0.5", children: eu.utility_type }), _jsx("td", { className: "py-0.5 text-right", children: eu.consumption_kw }), _jsx("td", { className: "py-0.5 text-right", children: eu.annual_cost?.toLocaleString() })] }, i))) })] })] }))] }))] })] }));
}
