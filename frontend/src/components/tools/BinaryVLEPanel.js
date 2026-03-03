import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { X, BarChart3 } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, } from 'recharts';
export default function BinaryVLEPanel({ open, onClose }) {
    const compounds = useFlowsheetStore((s) => s.simulationBasis.compounds);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    const [compA, setCompA] = useState('');
    const [compB, setCompB] = useState('');
    const [diagramType, setDiagramType] = useState('txy');
    const [pressure, setPressure] = useState(101.325); // kPa for Txy
    const [temperature, setTemperature] = useState(25); // °C for Pxy
    const [nPoints, setNPoints] = useState(51);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const canCompute = compA && compB && compA !== compB;
    const compute = async () => {
        if (!canCompute)
            return;
        setLoading(true);
        setError('');
        setResult(null);
        try {
            const endpoint = diagramType === 'pxy'
                ? '/api/simulation/binary-vle/pxy'
                : '/api/simulation/binary-vle/txy';
            const body = {
                comp_a: compA,
                comp_b: compB,
                property_package: propertyPackage,
                n_points: nPoints,
            };
            if (diagramType === 'pxy') {
                body.T = temperature + 273.15; // °C → K
            }
            else {
                body.P = pressure * 1000; // kPa → Pa
            }
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || `HTTP ${res.status}`);
            }
            const data = await res.json();
            setResult(data);
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to compute VLE diagram');
        }
        finally {
            setLoading(false);
        }
    };
    if (!open)
        return null;
    return (_jsxs("div", { className: "absolute right-0 top-0 h-full w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(BarChart3, { size: 16, className: "text-orange-400" }), _jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Binary VLE Diagrams" })] }), _jsx("button", { onClick: onClose, className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { className: "grid grid-cols-2 gap-3", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Component A" }), _jsxs("select", { value: compA, onChange: (e) => setCompA(e.target.value), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 text-gray-700 dark:text-gray-300", children: [_jsx("option", { value: "", children: "Select..." }), compounds.map((c) => (_jsx("option", { value: c, disabled: c === compB, children: c }, c)))] })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Component B" }), _jsxs("select", { value: compB, onChange: (e) => setCompB(e.target.value), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 text-gray-700 dark:text-gray-300", children: [_jsx("option", { value: "", children: "Select..." }), compounds.map((c) => (_jsx("option", { value: c, disabled: c === compA, children: c }, c)))] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Diagram Type" }), _jsx("div", { className: "flex gap-2", children: ['txy', 'pxy', 'xy'].map((t) => (_jsx("button", { onClick: () => setDiagramType(t), className: `px-3 py-1 text-xs rounded border ${diagramType === t
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-700'}`, children: t === 'txy' ? 'Txy' : t === 'pxy' ? 'Pxy' : 'x-y' }, t))) })] }), diagramType !== 'xy' && (_jsx("div", { children: diagramType === 'txy' ? (_jsxs(_Fragment, { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Pressure (kPa)" }), _jsx("input", { type: "number", value: pressure, onChange: (e) => setPressure(Number(e.target.value)), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300" })] })) : (_jsxs(_Fragment, { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Temperature (\u00B0C)" }), _jsx("input", { type: "number", value: temperature, onChange: (e) => setTemperature(Number(e.target.value)), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300" })] })) })), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Points" }), _jsx("input", { type: "number", value: nPoints, onChange: (e) => setNPoints(Math.min(200, Math.max(11, Number(e.target.value)))), min: 11, max: 200, className: "w-24 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300" })] }), _jsx("button", { onClick: compute, disabled: !canCompute || loading, className: "w-full py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed", children: loading ? 'Computing...' : 'Generate Diagram' }), error && (_jsx("div", { className: "text-xs text-red-500 bg-red-50 dark:bg-red-900/20 rounded p-2", children: error })), result && (_jsx("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-4", children: diagramType === 'xy' || (diagramType !== 'pxy' && diagramType !== 'txy' && result.xy_curve?.length > 0) ? (_jsx(XYDiagram, { data: result, compA: compA })) : diagramType === 'txy' ? (_jsx(TxyDiagram, { data: result, compA: compA })) : (_jsx(PxyDiagram, { data: result, compA: compA })) })), compounds.length < 2 && (_jsx("div", { className: "text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded p-3", children: "Add at least 2 compounds in the Simulation Basis panel to use binary VLE diagrams." }))] })] }));
}
function TxyDiagram({ data, compA }) {
    // Merge bubble and dew curves on x_a
    const merged = [];
    const map = new Map();
    for (const pt of data.bubble_curve) {
        const key = pt.x_a;
        const entry = map.get(key) || {};
        entry.T_bubble = pt.T_C;
        map.set(key, entry);
    }
    for (const pt of data.dew_curve) {
        const key = pt.x_a;
        const entry = map.get(key) || {};
        entry.T_dew = pt.T_C;
        map.set(key, entry);
    }
    for (const [x_a, vals] of Array.from(map.entries()).sort((a, b) => a[0] - b[0])) {
        merged.push({ x_a, ...vals });
    }
    return (_jsxs("div", { children: [_jsxs("h3", { className: "text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2", children: ["Txy Diagram \u2014 ", compA, " at ", data.P_kPa ?? '', " kPa"] }), _jsx(ResponsiveContainer, { width: "100%", height: 280, children: _jsxs(LineChart, { data: merged, margin: { top: 5, right: 10, left: 0, bottom: 5 }, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151", opacity: 0.3 }), _jsx(XAxis, { dataKey: "x_a", label: { value: `x, y (${compA})`, position: 'insideBottom', offset: -3, fontSize: 10 }, tick: { fontSize: 10 } }), _jsx(YAxis, { label: { value: 'T (°C)', angle: -90, position: 'insideLeft', fontSize: 10 }, tick: { fontSize: 10 } }), _jsx(Tooltip, { contentStyle: { fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' } }), _jsx(Legend, { wrapperStyle: { fontSize: 10 } }), _jsx(Line, { type: "monotone", dataKey: "T_bubble", name: "Bubble", stroke: "#3b82f6", dot: false, strokeWidth: 2 }), _jsx(Line, { type: "monotone", dataKey: "T_dew", name: "Dew", stroke: "#ef4444", dot: false, strokeWidth: 2 })] }) })] }));
}
function PxyDiagram({ data, compA }) {
    const merged = [];
    const map = new Map();
    for (const pt of data.bubble_curve) {
        const entry = map.get(pt.x_a) || {};
        entry.P_bubble = pt.P_kPa;
        map.set(pt.x_a, entry);
    }
    for (const pt of data.dew_curve) {
        const entry = map.get(pt.x_a) || {};
        entry.P_dew = pt.P_kPa;
        map.set(pt.x_a, entry);
    }
    for (const [x_a, vals] of Array.from(map.entries()).sort((a, b) => a[0] - b[0])) {
        merged.push({ x_a, ...vals });
    }
    return (_jsxs("div", { children: [_jsxs("h3", { className: "text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2", children: ["Pxy Diagram \u2014 ", compA, " at ", data.T_C ?? '', " \u00B0C"] }), _jsx(ResponsiveContainer, { width: "100%", height: 280, children: _jsxs(LineChart, { data: merged, margin: { top: 5, right: 10, left: 0, bottom: 5 }, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151", opacity: 0.3 }), _jsx(XAxis, { dataKey: "x_a", label: { value: `x, y (${compA})`, position: 'insideBottom', offset: -3, fontSize: 10 }, tick: { fontSize: 10 } }), _jsx(YAxis, { label: { value: 'P (kPa)', angle: -90, position: 'insideLeft', fontSize: 10 }, tick: { fontSize: 10 } }), _jsx(Tooltip, { contentStyle: { fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' } }), _jsx(Legend, { wrapperStyle: { fontSize: 10 } }), _jsx(Line, { type: "monotone", dataKey: "P_bubble", name: "Bubble", stroke: "#3b82f6", dot: false, strokeWidth: 2 }), _jsx(Line, { type: "monotone", dataKey: "P_dew", name: "Dew", stroke: "#ef4444", dot: false, strokeWidth: 2 })] }) })] }));
}
function XYDiagram({ data, compA }) {
    // x-y diagram + diagonal reference line
    const xyData = data.xy_curve.map((pt) => ({
        x: pt.x_a,
        y: pt.y_a,
        diagonal: pt.x_a,
    }));
    return (_jsxs("div", { children: [_jsxs("h3", { className: "text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2", children: ["x-y Diagram \u2014 ", compA] }), _jsx(ResponsiveContainer, { width: "100%", height: 280, children: _jsxs(LineChart, { data: xyData, margin: { top: 5, right: 10, left: 0, bottom: 5 }, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151", opacity: 0.3 }), _jsx(XAxis, { dataKey: "x", domain: [0, 1], label: { value: `x (${compA})`, position: 'insideBottom', offset: -3, fontSize: 10 }, tick: { fontSize: 10 } }), _jsx(YAxis, { domain: [0, 1], label: { value: `y (${compA})`, angle: -90, position: 'insideLeft', fontSize: 10 }, tick: { fontSize: 10 } }), _jsx(Tooltip, { contentStyle: { fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' } }), _jsx(Legend, { wrapperStyle: { fontSize: 10 } }), _jsx(Line, { type: "monotone", dataKey: "y", name: "VLE", stroke: "#3b82f6", dot: false, strokeWidth: 2 }), _jsx(Line, { type: "monotone", dataKey: "diagonal", name: "y=x", stroke: "#6b7280", dot: false, strokeWidth: 1, strokeDasharray: "5 5" })] }) })] }));
}
