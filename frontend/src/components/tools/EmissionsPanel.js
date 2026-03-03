import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
export default function EmissionsPanel({ open, onClose }) {
    const simResults = useSimulationStore((s) => s.results);
    const [fuelType, setFuelType] = useState('natural_gas');
    const [consumption, setConsumption] = useState(0);
    const [carbonPrice, setCarbonPrice] = useState(50);
    const [hoursPerYear, setHoursPerYear] = useState(8000);
    const [valves, setValves] = useState(0);
    const [pumps, setPumps] = useState(0);
    const [compressors, setCompressors] = useState(0);
    const [flanges, setFlanges] = useState(0);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const run = async () => {
        setRunning(true);
        setError('');
        try {
            const raw = simResults ? {
                stream_results: simResults.streamResults,
                equipment_results: simResults.equipmentResults,
            } : null;
            const res = await fetch('/api/simulation/emissions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    simulation_results: raw,
                    fuel: { fuel_type: fuelType, consumption },
                    equipment_counts: { valves, pumps, compressors, flanges },
                    carbon_price: carbonPrice,
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Environmental Calculations" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block", children: "Combustion" }), _jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Fuel Type" }), _jsxs("select", { value: fuelType, onChange: (e) => setFuelType(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "natural_gas", children: "Natural Gas" }), _jsx("option", { value: "fuel_oil", children: "Fuel Oil" }), _jsx("option", { value: "coal", children: "Coal" }), _jsx("option", { value: "lpg", children: "LPG" })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Consumption (GJ/hr, 0=auto)" }), _jsx("input", { type: "number", value: consumption, onChange: (e) => setConsumption(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block", children: "Fugitive Equipment Counts" }), _jsxs("div", { className: "grid grid-cols-4 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Valves" }), _jsx("input", { type: "number", value: valves, min: 0, onChange: (e) => setValves(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Pumps" }), _jsx("input", { type: "number", value: pumps, min: 0, onChange: (e) => setPumps(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Compr." }), _jsx("input", { type: "number", value: compressors, min: 0, onChange: (e) => setCompressors(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Flanges" }), _jsx("input", { type: "number", value: flanges, min: 0, onChange: (e) => setFlanges(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })] }), _jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Carbon Price ($/t CO2e)" }), _jsx("input", { type: "number", value: carbonPrice, onChange: (e) => setCarbonPrice(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Hours/Year" }), _jsx("input", { type: "number", value: hoursPerYear, onChange: (e) => setHoursPerYear(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] }), _jsxs("button", { onClick: run, disabled: running, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Computing...' : 'Calculate Emissions'] }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-2", children: [_jsx("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: "Results (tonnes/year)" }), _jsxs("div", { className: "grid grid-cols-2 gap-1 text-xs text-gray-600 dark:text-gray-400", children: [_jsx("span", { children: "CO2:" }), _jsx("span", { className: "text-right", children: results.combustion_co2_tpy?.toFixed(1) }), _jsx("span", { children: "NOx:" }), _jsx("span", { className: "text-right", children: results.combustion_nox_tpy?.toFixed(3) }), _jsx("span", { children: "SOx:" }), _jsx("span", { className: "text-right", children: results.combustion_sox_tpy?.toFixed(3) }), _jsx("span", { children: "CO:" }), _jsx("span", { className: "text-right", children: results.combustion_co_tpy?.toFixed(3) }), _jsx("span", { children: "PM:" }), _jsx("span", { className: "text-right", children: results.combustion_pm_tpy?.toFixed(3) }), _jsx("span", { children: "Fugitive VOC:" }), _jsx("span", { className: "text-right", children: results.fugitive_voc_tpy?.toFixed(3) }), _jsx("span", { children: "Fugitive CH4:" }), _jsx("span", { className: "text-right", children: results.fugitive_methane_tpy?.toFixed(3) })] }), _jsxs("div", { className: "border-t border-gray-200 dark:border-gray-700 pt-1", children: [_jsxs("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: ["Total CO2e: ", results.total_co2e_tpy?.toFixed(1), " t/yr"] }), _jsxs("div", { className: "text-xs font-semibold text-green-500", children: ["Carbon Cost: $", results.carbon_cost_annual?.toLocaleString(), "/yr"] })] })] }))] })] }));
}
