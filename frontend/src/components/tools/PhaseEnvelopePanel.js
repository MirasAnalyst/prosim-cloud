import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useMemo } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceDot } from 'recharts';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { API_BASE } from '../../lib/api-client';
export default function PhaseEnvelopePanel({ open, onClose }) {
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const [nPoints, setNPoints] = useState(80);
    // Get compounds from simulation basis
    const basisCompounds = useMemo(() => {
        return simulationBasis?.compounds ?? [];
    }, [simulationBasis]);
    const [composition, setComposition] = useState({});
    // Initialize composition from basis if empty
    useMemo(() => {
        if (basisCompounds.length > 0 && Object.keys(composition).length === 0) {
            const equal = 1.0 / basisCompounds.length;
            const init = {};
            basisCompounds.forEach((c) => { init[c] = parseFloat(equal.toFixed(4)); });
            setComposition(init);
        }
    }, [basisCompounds]);
    const propertyPackage = simulationBasis?.property_package ?? 'PengRobinson';
    const runEnvelope = async () => {
        const compounds = Object.keys(composition);
        const zs = Object.values(composition);
        if (compounds.length === 0) {
            setError('Add compounds to simulation basis first');
            return;
        }
        setRunning(true);
        setError('');
        setResults(null);
        try {
            const res = await fetch(`${API_BASE}/api/simulation/phase-envelope`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    compounds,
                    composition: zs,
                    property_package: propertyPackage,
                    n_points: nPoints,
                }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to compute phase envelope');
            }
            const data = await res.json();
            setResults(data);
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        }
        finally {
            setRunning(false);
        }
    };
    if (!open)
        return null;
    return (_jsxs("div", { className: "fixed inset-y-0 right-0 w-[600px] bg-white dark:bg-gray-900 shadow-xl z-50 flex flex-col border-l border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h2", { className: "font-semibold text-gray-800 dark:text-gray-200", children: "Phase Envelope" }), _jsx("button", { onClick: onClose, className: "p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("h3", { className: "text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2", children: "Composition (mole fractions)" }), basisCompounds.length === 0 ? (_jsx("p", { className: "text-xs text-gray-400", children: "No compounds in simulation basis. Add compounds first." })) : (_jsx("div", { className: "space-y-1", children: basisCompounds.map((comp) => (_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "text-xs text-gray-600 dark:text-gray-400 w-32 truncate", children: comp }), _jsx("input", { type: "number", step: "0.01", min: "0", max: "1", value: composition[comp] ?? 0, onChange: (e) => setComposition({ ...composition, [comp]: parseFloat(e.target.value) || 0 }), className: "w-24 px-2 py-1 text-xs border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200" })] }, comp))) }))] }), _jsxs("div", { className: "flex items-center gap-4", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "text-xs text-gray-500", children: "Points:" }), _jsx("input", { type: "number", min: "20", max: "200", value: nPoints, onChange: (e) => setNPoints(parseInt(e.target.value) || 50), className: "w-16 px-2 py-1 text-xs border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200" })] }), _jsx("span", { className: "text-xs text-gray-400", children: propertyPackage })] }), _jsxs("button", { onClick: runEnvelope, disabled: running || basisCompounds.length === 0, className: "flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Computing...' : 'Generate Envelope'] }), error && (_jsx("div", { className: "p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400", children: error })), results && (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3", children: [_jsx("h3", { className: "text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2", children: "PT Phase Envelope" }), _jsx(ResponsiveContainer, { width: "100%", height: 350, children: _jsxs(LineChart, { margin: { top: 5, right: 20, bottom: 20, left: 20 }, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151" }), _jsx(XAxis, { dataKey: "T_C", type: "number", domain: ['auto', 'auto'], label: { value: 'Temperature (\u00B0C)', position: 'bottom', offset: 5, style: { fontSize: 11 } }, tick: { fontSize: 10 }, allowDuplicatedCategory: false }), _jsx(YAxis, { dataKey: "P_kPa", type: "number", domain: ['auto', 'auto'], label: { value: 'Pressure (kPa)', angle: -90, position: 'left', offset: 5, style: { fontSize: 11 } }, tick: { fontSize: 10 } }), _jsx(Tooltip, { formatter: (value) => [typeof value === 'number' ? value.toFixed(1) : String(value)], labelFormatter: (label) => `T = ${typeof label === 'number' ? label.toFixed(1) : label} \u00B0C`, contentStyle: { fontSize: 11, backgroundColor: '#1f2937', border: '1px solid #374151' } }), _jsx(Legend, { wrapperStyle: { fontSize: 11 } }), _jsx(Line, { data: results.bubble_curve, dataKey: "P_kPa", name: "Bubble Point", stroke: "#3b82f6", dot: false, strokeWidth: 2 }), _jsx(Line, { data: results.dew_curve, dataKey: "P_kPa", name: "Dew Point", stroke: "#ef4444", dot: false, strokeWidth: 2 }), results.critical_point && (_jsx(ReferenceDot, { x: results.critical_point.T_C, y: results.critical_point.P_kPa, r: 5, fill: "#f59e0b", stroke: "#f59e0b" }))] }) })] }), _jsxs("div", { className: "grid grid-cols-3 gap-3 text-xs", children: [results.critical_point && (_jsxs("div", { className: "bg-yellow-500/10 border border-yellow-500/30 rounded p-2", children: [_jsx("div", { className: "font-semibold text-yellow-400 mb-1", children: "Critical Point" }), _jsxs("div", { className: "text-gray-400", children: ["T: ", results.critical_point.T_C.toFixed(1), " \u00B0C"] }), _jsxs("div", { className: "text-gray-400", children: ["P: ", results.critical_point.P_kPa.toFixed(1), " kPa"] })] })), results.cricondentherm && (_jsxs("div", { className: "bg-red-500/10 border border-red-500/30 rounded p-2", children: [_jsx("div", { className: "font-semibold text-red-400 mb-1", children: "Cricondentherm" }), _jsxs("div", { className: "text-gray-400", children: ["T: ", results.cricondentherm.T_C.toFixed(1), " \u00B0C"] }), _jsxs("div", { className: "text-gray-400", children: ["P: ", results.cricondentherm.P_kPa.toFixed(1), " kPa"] })] })), results.cricondenbar && (_jsxs("div", { className: "bg-blue-500/10 border border-blue-500/30 rounded p-2", children: [_jsx("div", { className: "font-semibold text-blue-400 mb-1", children: "Cricondenbar" }), _jsxs("div", { className: "text-gray-400", children: ["T: ", results.cricondenbar.T_C.toFixed(1), " \u00B0C"] }), _jsxs("div", { className: "text-gray-400", children: ["P: ", results.cricondenbar.P_kPa.toFixed(1), " kPa"] })] }))] })] }))] })] }));
}
