import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { API_BASE } from '../../lib/api-client';
const RESULT_KEYS = [
    { value: 'duty', label: 'Duty (kW)' },
    { value: 'work', label: 'Work (kW)' },
    { value: 'outletTemperature', label: 'Outlet Temp (°C)' },
    { value: 'vaporFraction', label: 'Vapor Fraction' },
    { value: 'massFlow', label: 'Mass Flow (kg/s)' },
    { value: 'outletPressure', label: 'Outlet Pressure (kPa)' },
];
export default function OptimizationPanel({ open, onClose }) {
    const nodes = useFlowsheetStore((s) => s.nodes);
    const edges = useFlowsheetStore((s) => s.edges);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const [objNodeId, setObjNodeId] = useState('');
    const [objKey, setObjKey] = useState('');
    const [objSense, setObjSense] = useState('minimize');
    const [solver, setSolver] = useState('SLSQP');
    const [maxIter, setMaxIter] = useState(100);
    const [dvars, setDvars] = useState([]);
    const [constraints, setConstraints] = useState([]);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const equipmentNodes = nodes.filter((n) => {
        const t = n.data?.equipmentType || n.type;
        return t && t !== 'equipment';
    });
    const getParamKeys = (nodeId) => {
        const node = nodes.find((n) => n.id === nodeId);
        if (!node)
            return [];
        const eqType = node.data?.equipmentType;
        if (!eqType || !(eqType in equipmentLibrary))
            return [];
        return Object.keys(equipmentLibrary[eqType].parameters);
    };
    const addDvar = () => setDvars([...dvars, { nodeId: '', paramKey: '', min: 0, max: 100 }]);
    const addConstraint = () => setConstraints([...constraints, { nodeId: '', resultKey: '', operator: '<=', value: 0 }]);
    const run = async () => {
        if (!objNodeId || !objKey || dvars.length === 0)
            return;
        setRunning(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/simulation/optimize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_nodes: nodes,
                    base_edges: edges.map((e) => ({ ...e, type: e.type ?? 'stream' })),
                    property_package: propertyPackage,
                    simulation_basis: simulationBasis,
                    objective: { node_id: objNodeId, result_key: objKey, sense: objSense },
                    decision_variables: dvars.map((d) => ({
                        node_id: d.nodeId, parameter_key: d.paramKey,
                        min_value: d.min, max_value: d.max,
                    })),
                    constraints: constraints.map((c) => ({
                        node_id: c.nodeId, result_key: c.resultKey,
                        operator: c.operator, value: c.value,
                    })),
                    solver,
                    max_iterations: maxIter,
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Optimization" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1", children: "Objective" }), _jsxs("div", { className: "flex gap-1", children: [_jsxs("select", { value: objNodeId, onChange: (e) => setObjNodeId(e.target.value), className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "", children: "Equipment" }), equipmentNodes.map((n) => _jsx("option", { value: n.id, children: n.data?.name || n.id.slice(0, 8) }, n.id))] }), _jsxs("select", { value: objKey, onChange: (e) => setObjKey(e.target.value), className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "", children: "Result" }), RESULT_KEYS.map((k) => _jsx("option", { value: k.value, children: k.label }, k.value))] }), _jsxs("select", { value: objSense, onChange: (e) => setObjSense(e.target.value), className: "text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "minimize", children: "Min" }), _jsx("option", { value: "maximize", children: "Max" })] })] })] }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center justify-between mb-1", children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400", children: "Decision Variables" }), _jsx("button", { onClick: addDvar, className: "text-xs text-blue-500 hover:text-blue-400", children: "+ Add" })] }), dvars.map((dv, i) => (_jsxs("div", { className: "flex gap-1 mb-1", children: [_jsxs("select", { value: dv.nodeId, onChange: (e) => { const d = [...dvars]; d[i].nodeId = e.target.value; setDvars(d); }, className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5", children: [_jsx("option", { value: "", children: "Equip" }), equipmentNodes.map((n) => _jsx("option", { value: n.id, children: n.data?.name || n.id.slice(0, 8) }, n.id))] }), _jsxs("select", { value: dv.paramKey, onChange: (e) => { const d = [...dvars]; d[i].paramKey = e.target.value; setDvars(d); }, className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5", children: [_jsx("option", { value: "", children: "Param" }), dv.nodeId && getParamKeys(dv.nodeId).map((k) => _jsx("option", { value: k, children: k }, k))] }), _jsx("input", { type: "number", placeholder: "Min", value: dv.min, onChange: (e) => { const d = [...dvars]; d[i].min = Number(e.target.value); setDvars(d); }, className: "w-14 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" }), _jsx("input", { type: "number", placeholder: "Max", value: dv.max, onChange: (e) => { const d = [...dvars]; d[i].max = Number(e.target.value); setDvars(d); }, className: "w-14 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" }), _jsx("button", { onClick: () => setDvars(dvars.filter((_, j) => j !== i)), className: "text-red-400 text-xs", children: "\u00D7" })] }, i)))] }), _jsxs("div", { children: [_jsxs("div", { className: "flex items-center justify-between mb-1", children: [_jsx("label", { className: "text-xs font-medium text-gray-500 dark:text-gray-400", children: "Constraints" }), _jsx("button", { onClick: addConstraint, className: "text-xs text-blue-500 hover:text-blue-400", children: "+ Add" })] }), constraints.map((c, i) => (_jsxs("div", { className: "flex gap-1 mb-1", children: [_jsxs("select", { value: c.nodeId, onChange: (e) => { const cs = [...constraints]; cs[i].nodeId = e.target.value; setConstraints(cs); }, className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5", children: [_jsx("option", { value: "", children: "Equip" }), equipmentNodes.map((n) => _jsx("option", { value: n.id, children: n.data?.name || n.id.slice(0, 8) }, n.id))] }), _jsxs("select", { value: c.resultKey, onChange: (e) => { const cs = [...constraints]; cs[i].resultKey = e.target.value; setConstraints(cs); }, className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5", children: [_jsx("option", { value: "", children: "Result" }), RESULT_KEYS.map((k) => _jsx("option", { value: k.value, children: k.label }, k.value))] }), _jsxs("select", { value: c.operator, onChange: (e) => { const cs = [...constraints]; cs[i].operator = e.target.value; setConstraints(cs); }, className: "w-12 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5", children: [_jsx("option", { value: "<=", children: "\u2264" }), _jsx("option", { value: ">=", children: "\u2265" }), _jsx("option", { value: "==", children: "=" })] }), _jsx("input", { type: "number", value: c.value, onChange: (e) => { const cs = [...constraints]; cs[i].value = Number(e.target.value); setConstraints(cs); }, className: "w-16 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" }), _jsx("button", { onClick: () => setConstraints(constraints.filter((_, j) => j !== i)), className: "text-red-400 text-xs", children: "\u00D7" })] }, i)))] }), _jsxs("div", { className: "flex gap-2", children: [_jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Solver" }), _jsxs("select", { value: solver, onChange: (e) => setSolver(e.target.value), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "SLSQP", children: "SLSQP" }), _jsx("option", { value: "differential_evolution", children: "Differential Evolution" })] })] }), _jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Max Iterations" }), _jsx("input", { type: "number", value: maxIter, onChange: (e) => setMaxIter(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] }), _jsxs("button", { onClick: run, disabled: running, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Optimizing...' : 'Optimize'] }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && (_jsxs("div", { className: "space-y-2", children: [_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800 rounded p-3", children: [_jsxs("div", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1", children: ["Status: ", results.status, " | Iterations: ", results.iterations] }), results.objective_value != null && (_jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400", children: ["Objective: ", results.objective_value] })), _jsx("div", { className: "text-xs font-medium text-gray-600 dark:text-gray-400 mt-2", children: "Optimal Values:" }), Object.entries(results.optimal_values || {}).map(([k, v]) => (_jsxs("div", { className: "text-xs text-gray-500", children: [k, ": ", String(v)] }, k))), results.message && _jsx("div", { className: "text-xs text-gray-500 mt-1", children: results.message })] }), results.convergence_history && results.convergence_history.length > 1 && (_jsx("div", { className: "h-48", children: _jsx(ResponsiveContainer, { width: "100%", height: "100%", children: _jsxs(LineChart, { data: results.convergence_history.map((v, i) => ({ iter: i, value: v })), children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151" }), _jsx(XAxis, { dataKey: "iter", tick: { fontSize: 10 } }), _jsx(YAxis, { tick: { fontSize: 10 } }), _jsx(Tooltip, { contentStyle: { fontSize: 10, backgroundColor: '#1F2937', border: 'none' } }), _jsx(Line, { type: "monotone", dataKey: "value", stroke: "#3B82F6", dot: false })] }) }) }))] }))] })] }));
}
