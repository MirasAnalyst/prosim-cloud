import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { API_BASE } from '../../lib/api-client';
export default function ReliefValvePanel({ open, onClose }) {
    const [phase, setPhase] = useState('gas');
    const [scenario, setScenario] = useState('blocked_outlet');
    const [setPressure, setSetPressure] = useState(1000);
    const [backpressure, setBackpressure] = useState(101.325);
    const [overpressure, setOverpressure] = useState(10);
    const [massFlow, setMassFlow] = useState(5000);
    const [mw, setMw] = useState(28.97);
    const [temperature, setTemperature] = useState(25);
    const [kRatio, setKRatio] = useState(1.4);
    const [volFlow, setVolFlow] = useState(10);
    const [sg, setSg] = useState(1.0);
    const [wettedArea, setWettedArea] = useState(50);
    const [insulFactor, setInsulFactor] = useState(1.0);
    const [latentHeat, setLatentHeat] = useState(200);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const run = async () => {
        setRunning(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/simulation/relief-valve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phase, scenario,
                    set_pressure: setPressure,
                    backpressure,
                    overpressure_pct: overpressure,
                    mass_flow_rate: massFlow,
                    molecular_weight: mw,
                    temperature,
                    k_ratio: kRatio,
                    volumetric_flow: volFlow,
                    specific_gravity: sg,
                    wetted_area: wettedArea,
                    insulation_factor: insulFactor,
                    latent_heat: latentHeat,
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[420px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Relief Valve Sizing" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-3", children: [_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Phase" }), _jsxs("select", { value: phase, onChange: (e) => setPhase(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "gas", children: "Gas" }), _jsx("option", { value: "liquid", children: "Liquid" }), _jsx("option", { value: "two_phase", children: "Two-Phase" })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Scenario" }), _jsxs("select", { value: scenario, onChange: (e) => setScenario(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "blocked_outlet", children: "Blocked Outlet" }), _jsx("option", { value: "fire", children: "Fire Case" }), _jsx("option", { value: "thermal_expansion", children: "Thermal Expansion" })] })] })] }), _jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Set P (kPa)" }), _jsx("input", { type: "number", value: setPressure, onChange: (e) => setSetPressure(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Back P (kPa)" }), _jsx("input", { type: "number", value: backpressure, onChange: (e) => setBackpressure(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Overpress %" }), _jsx("input", { type: "number", value: overpressure, onChange: (e) => setOverpressure(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] }), (phase === 'gas' || phase === 'two_phase') && (_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Mass Flow (kg/hr)" }), _jsx("input", { type: "number", value: massFlow, onChange: (e) => setMassFlow(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "MW (g/mol)" }), _jsx("input", { type: "number", value: mw, onChange: (e) => setMw(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Temperature (\u00B0C)" }), _jsx("input", { type: "number", value: temperature, onChange: (e) => setTemperature(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "k (Cp/Cv)" }), _jsx("input", { type: "number", value: kRatio, step: 0.01, onChange: (e) => setKRatio(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })), phase === 'liquid' && (_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Vol Flow (m\u00B3/hr)" }), _jsx("input", { type: "number", value: volFlow, onChange: (e) => setVolFlow(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Specific Gravity" }), _jsx("input", { type: "number", value: sg, step: 0.01, onChange: (e) => setSg(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })), scenario === 'fire' && (_jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Wetted Area (m\u00B2)" }), _jsx("input", { type: "number", value: wettedArea, onChange: (e) => setWettedArea(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Insulation F" }), _jsx("input", { type: "number", value: insulFactor, step: 0.1, onChange: (e) => setInsulFactor(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Latent Heat (kJ/kg)" }), _jsx("input", { type: "number", value: latentHeat, onChange: (e) => setLatentHeat(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })), _jsxs("button", { onClick: run, disabled: running, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Sizing...' : 'Size Relief Valve'] }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1", children: [_jsx("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: "Results" }), _jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Required Area: ", results.required_area_mm2, " mm\u00B2 (", results.required_area_in2, " in\u00B2)"] }), _jsxs("div", { className: "text-xs font-semibold text-blue-400", children: ["Selected Orifice: ", results.selected_orifice, " (", results.orifice_area_mm2, " mm\u00B2)"] }), _jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Relieving Pressure: ", results.relieving_pressure_kpa, " kPa"] }), _jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Mass Flow: ", results.mass_flow_kg_hr, " kg/hr"] }), _jsx("div", { className: "text-[10px] text-yellow-500 mt-2", children: results.disclaimer })] }))] })] }));
}
