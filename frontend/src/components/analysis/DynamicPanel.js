import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
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
const COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];
export default function DynamicPanel({ open, onClose }) {
    const nodes = useFlowsheetStore((s) => s.nodes);
    const edges = useFlowsheetStore((s) => s.edges);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const [disturbance, setDisturbance] = useState({ nodeId: '', parameterKey: '', stepSize: 10 });
    const [outputs, setOutputs] = useState([]);
    const [timeHorizon, setTimeHorizon] = useState(3600);
    const [timeSteps, setTimeSteps] = useState(50);
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const [newOutNodeId, setNewOutNodeId] = useState('');
    const [newOutKey, setNewOutKey] = useState('');
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
    const addOutput = () => {
        if (!newOutNodeId || !newOutKey)
            return;
        const node = nodes.find((n) => n.id === newOutNodeId);
        const name = node?.data?.name || newOutNodeId.slice(0, 8);
        setOutputs([...outputs, { nodeId: newOutNodeId, resultKey: newOutKey, label: `${name}.${newOutKey}` }]);
        setNewOutNodeId('');
        setNewOutKey('');
    };
    const run = async () => {
        if (!disturbance.nodeId || !disturbance.parameterKey || outputs.length === 0)
            return;
        setRunning(true);
        setError('');
        try {
            const res = await fetch(`${API_BASE}/api/simulation/dynamic`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_nodes: nodes,
                    base_edges: edges.map((e) => ({ ...e, type: e.type ?? 'stream' })),
                    property_package: propertyPackage,
                    simulation_basis: simulationBasis,
                    disturbances: [{ node_id: disturbance.nodeId, parameter_key: disturbance.parameterKey, step_size: disturbance.stepSize }],
                    tracked_outputs: outputs.map((o) => ({ node_id: o.nodeId, result_key: o.resultKey, label: o.label })),
                    time_horizon: timeHorizon,
                    time_steps: timeSteps,
                }),
            });
            const data = await res.json();
            if (data.error) {
                setError(data.error);
            }
            else {
                const chartData = (data.time_values || []).map((t, i) => {
                    const row = { time: t };
                    for (const [key, vals] of Object.entries(data.output_trajectories || {})) {
                        row[key] = vals[i];
                    }
                    return row;
                });
                setResults(chartData);
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
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Dynamic Simulation" }), _jsx("button", { onClick: onClose, className: "text-gray-400 hover:text-gray-600", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1", children: "Disturbance" }), _jsxs("select", { value: disturbance.nodeId, onChange: (e) => setDisturbance({ ...disturbance, nodeId: e.target.value }), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 mb-1", children: [_jsx("option", { value: "", children: "Select equipment" }), equipmentNodes.map((n) => _jsx("option", { value: n.id, children: n.data?.name || n.id.slice(0, 8) }, n.id))] }), disturbance.nodeId && (_jsxs("select", { value: disturbance.parameterKey, onChange: (e) => setDisturbance({ ...disturbance, parameterKey: e.target.value }), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 mb-1", children: [_jsx("option", { value: "", children: "Select parameter" }), getParamKeys(disturbance.nodeId).map((k) => _jsx("option", { value: k, children: k }, k))] })), _jsxs("div", { className: "flex gap-2", children: [_jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Step Size" }), _jsx("input", { type: "number", value: disturbance.stepSize, onChange: (e) => setDisturbance({ ...disturbance, stepSize: Number(e.target.value) }), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Time (s)" }), _jsx("input", { type: "number", value: timeHorizon, onChange: (e) => setTimeHorizon(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] }), _jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Steps" }), _jsx("input", { type: "number", value: timeSteps, onChange: (e) => setTimeSteps(Number(e.target.value)), className: "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" })] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1", children: "Tracked Outputs" }), outputs.map((o, i) => (_jsxs("div", { className: "flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 mb-1", children: [_jsx("span", { className: "flex-1 truncate", children: o.label }), _jsx("button", { onClick: () => setOutputs(outputs.filter((_, j) => j !== i)), className: "text-red-400 hover:text-red-600", children: "\u00D7" })] }, i))), _jsxs("div", { className: "flex gap-1", children: [_jsxs("select", { value: newOutNodeId, onChange: (e) => setNewOutNodeId(e.target.value), className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "", children: "Equipment" }), equipmentNodes.map((n) => _jsx("option", { value: n.id, children: n.data?.name || n.id.slice(0, 8) }, n.id))] }), _jsxs("select", { value: newOutKey, onChange: (e) => setNewOutKey(e.target.value), className: "flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1", children: [_jsx("option", { value: "", children: "Result key" }), RESULT_KEYS.map((k) => _jsx("option", { value: k.value, children: k.label }, k.value))] }), _jsx("button", { onClick: addOutput, className: "text-xs text-blue-500 hover:text-blue-400", children: "Add" })] })] }), _jsxs("button", { onClick: run, disabled: running, className: "w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50", children: [running ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), running ? 'Running...' : 'Run Dynamic'] }), error && _jsx("div", { className: "text-xs text-red-400", children: error }), results && results.length > 0 && (_jsx("div", { className: "h-64", children: _jsx(ResponsiveContainer, { width: "100%", height: "100%", children: _jsxs(LineChart, { data: results, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151" }), _jsx(XAxis, { dataKey: "time", tick: { fontSize: 10 }, label: { value: 'Time (s)', position: 'bottom', fontSize: 10 } }), _jsx(YAxis, { tick: { fontSize: 10 } }), _jsx(Tooltip, { contentStyle: { fontSize: 10, backgroundColor: '#1F2937', border: 'none' } }), _jsx(Legend, { wrapperStyle: { fontSize: 10 } }), outputs.map((o, i) => {
                                        const key = `${o.nodeId}.${o.resultKey}`;
                                        return _jsx(Line, { type: "monotone", dataKey: key, stroke: COLORS[i % COLORS.length], dot: false, name: o.label }, key);
                                    })] }) }) }))] })] }));
}
