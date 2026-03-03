import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { API_BASE } from '../../lib/api-client';
export default function ControlValvePanel({ open, onClose }) {
    const [phase, setPhase] = useState('liquid');
    const [valveType, setValveType] = useState('globe');
    const [inletP, setInletP] = useState(500);
    const [outletP, setOutletP] = useState(300);
    const [temperature, setTemperature] = useState(25);
    const [volFlow, setVolFlow] = useState(10);
    const [sg, setSg] = useState(1.0);
    const [massFlow, setMassFlow] = useState(5000);
    const [mw, setMw] = useState(28.97);
    const [kRatio] = useState(1.4);
    const [pipeDia, setPipeDia] = useState(0.1);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const run = async () => {
        setRunning(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/simulation/control-valve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phase,
                    valve_type: valveType,
                    inlet_pressure: inletP,
                    outlet_pressure: outletP,
                    temperature,
                    volumetric_flow: volFlow,
                    specific_gravity: sg,
                    mass_flow_rate: massFlow,
                    molecular_weight: mw,
                    k_ratio: kRatio,
                    pipe_diameter: pipeDia,
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[420px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Control Valve Sizing" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-3", children: [_jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Phase" }), _jsxs("select", { value: phase, onChange: (e) => setPhase(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "liquid", children: "Liquid" }), _jsx("option", { value: "gas", children: "Gas" })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Valve Type" }), _jsxs("select", { value: valveType, onChange: (e) => setValveType(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "globe", children: "Globe" }), _jsx("option", { value: "butterfly", children: "Butterfly" }), _jsx("option", { value: "ball", children: "Ball" })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Pipe Dia (m)" }), _jsx("input", { type: "number", value: pipeDia, step: 0.01, onChange: (e) => setPipeDia(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] }), _jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Inlet P (kPa)" }), _jsx("input", { type: "number", value: inletP, onChange: (e) => setInletP(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Outlet P (kPa)" }), _jsx("input", { type: "number", value: outletP, onChange: (e) => setOutletP(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Temp (\u00B0C)" }), _jsx("input", { type: "number", value: temperature, onChange: (e) => setTemperature(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] }), phase === 'liquid' ? (_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Vol Flow (m\u00B3/hr)" }), _jsx("input", { type: "number", value: volFlow, onChange: (e) => setVolFlow(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Specific Gravity" }), _jsx("input", { type: "number", value: sg, step: 0.01, onChange: (e) => setSg(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })) : (_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Mass Flow (kg/hr)" }), _jsx("input", { type: "number", value: massFlow, onChange: (e) => setMassFlow(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "MW (g/mol)" }), _jsx("input", { type: "number", value: mw, onChange: (e) => setMw(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })), _jsxs("button", { onClick: run, disabled: running, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Sizing...' : 'Size Control Valve'] }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1", children: [_jsx("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: "Results" }), _jsxs("div", { className: "grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-600 dark:text-gray-400", children: [_jsx("span", { children: "Calculated Cv:" }), _jsx("span", { className: "text-right", children: results.calculated_cv }), _jsx("span", { children: "Selected Cv:" }), _jsx("span", { className: "text-right font-semibold text-blue-400", children: results.selected_cv }), _jsx("span", { children: "% Open:" }), _jsxs("span", { className: "text-right", children: [results.percent_open, "%"] }), _jsx("span", { children: "FL:" }), _jsx("span", { className: "text-right", children: results.fl }), _jsx("span", { children: "xT:" }), _jsx("span", { className: "text-right", children: results.xt }), _jsx("span", { children: "Flow Regime:" }), _jsx("span", { className: `text-right ${results.choked ? 'text-red-400' : 'text-green-500'}`, children: results.flow_regime }), results.choked && (_jsxs(_Fragment, { children: [_jsx("span", { children: "Choked \u0394P:" }), _jsxs("span", { className: "text-right text-red-400", children: [results.choked_dp_kpa, " kPa"] })] }))] })] }))] })] }));
}
