import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
export default function HydraulicsPanel({ open, onClose }) {
    const [massFlow, setMassFlow] = useState(10);
    const [density, setDensity] = useState(1000);
    const [viscosity, setViscosity] = useState(0.001);
    const [phase] = useState('liquid');
    const [length, setLength] = useState(100);
    const [diameter, setDiameter] = useState(0.1);
    const [roughness, setRoughness] = useState(0.000045);
    const [elevation, setElevation] = useState(0);
    const [elbows90, setElbows90] = useState(0);
    const [tees, setTees] = useState(0);
    const [gateValves, setGateValves] = useState(0);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const run = async () => {
        setRunning(true);
        setError('');
        try {
            const res = await fetch('/api/simulation/hydraulics', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mass_flow_rate: massFlow,
                    density,
                    viscosity,
                    phase,
                    length,
                    diameter,
                    roughness,
                    elevation,
                    elbows_90: elbows90,
                    tees,
                    gate_valves: gateValves,
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[420px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Pipe Hydraulics" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-3", children: [_jsxs("div", { children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block", children: "Fluid Properties" }), _jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Flow (kg/s)" }), _jsx("input", { type: "number", value: massFlow, step: 0.1, onChange: (e) => setMassFlow(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Density (kg/m\u00B3)" }), _jsx("input", { type: "number", value: density, onChange: (e) => setDensity(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Viscosity (Pa\u00B7s)" }), _jsx("input", { type: "number", value: viscosity, step: 0.0001, onChange: (e) => setViscosity(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block", children: "Pipe Geometry" }), _jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Length (m)" }), _jsx("input", { type: "number", value: length, onChange: (e) => setLength(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Diameter (m)" }), _jsx("input", { type: "number", value: diameter, step: 0.001, onChange: (e) => setDiameter(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Roughness (m)" }), _jsx("input", { type: "number", value: roughness, step: 0.00001, onChange: (e) => setRoughness(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Elevation (m)" }), _jsx("input", { type: "number", value: elevation, onChange: (e) => setElevation(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block", children: "Fittings" }), _jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "90\u00B0 Elbows" }), _jsx("input", { type: "number", value: elbows90, min: 0, onChange: (e) => setElbows90(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Tees" }), _jsx("input", { type: "number", value: tees, min: 0, onChange: (e) => setTees(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Gate Valves" }), _jsx("input", { type: "number", value: gateValves, min: 0, onChange: (e) => setGateValves(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })] }), _jsxs("button", { onClick: run, disabled: running, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Computing...' : 'Calculate Hydraulics'] }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1", children: [_jsx("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: "Results" }), _jsxs("div", { className: "grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-600 dark:text-gray-400", children: [_jsx("span", { children: "Total \u0394P:" }), _jsxs("span", { className: "text-right", children: [results.pressure_drop_kpa, " kPa"] }), _jsx("span", { children: "Friction \u0394P:" }), _jsxs("span", { className: "text-right", children: [results.pressure_drop_friction_kpa, " kPa"] }), _jsx("span", { children: "Elevation \u0394P:" }), _jsxs("span", { className: "text-right", children: [results.pressure_drop_elevation_kpa, " kPa"] }), _jsx("span", { children: "Fittings \u0394P:" }), _jsxs("span", { className: "text-right", children: [results.pressure_drop_fittings_kpa, " kPa"] }), _jsx("span", { children: "Velocity:" }), _jsxs("span", { className: "text-right", children: [results.velocity_m_s, " m/s"] }), _jsx("span", { children: "Reynolds:" }), _jsx("span", { className: "text-right", children: results.reynolds_number }), _jsx("span", { children: "Friction Factor:" }), _jsx("span", { className: "text-right", children: results.friction_factor }), _jsx("span", { children: "Flow Regime:" }), _jsx("span", { className: "text-right", children: results.flow_regime }), _jsx("span", { children: "Erosional V:" }), _jsxs("span", { className: "text-right", children: [results.erosional_velocity_m_s, " m/s"] }), _jsx("span", { children: "V/V_e Ratio:" }), _jsx("span", { className: `text-right ${results.erosional_ok ? 'text-green-500' : 'text-red-400'}`, children: results.erosional_ratio })] })] }))] })] }));
}
