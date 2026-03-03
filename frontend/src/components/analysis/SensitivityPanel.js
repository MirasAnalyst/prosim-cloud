import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { X, Play, Loader2, LineChart } from 'lucide-react';
import { LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { EquipmentType } from '../../types';
import { API_BASE } from '../../lib/api-client';
const RESULT_KEYS = [
    { value: 'duty', label: 'Duty (kW)' },
    { value: 'work', label: 'Work (kW)' },
    { value: 'outletTemperature', label: 'Outlet Temperature (°C)' },
    { value: 'vaporFraction', label: 'Vapor Fraction' },
    { value: 'massFlow', label: 'Mass Flow (kg/s)' },
    { value: 'outletPressure', label: 'Outlet Pressure (kPa)' },
    { value: 'pressureDrop', label: 'Pressure Drop (kPa)' },
];
const COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];
export default function SensitivityPanel({ open, onClose }) {
    const nodes = useFlowsheetStore((s) => s.nodes);
    const edges = useFlowsheetStore((s) => s.edges);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const [variableNodeId, setVariableNodeId] = useState('');
    const [variableParamKey, setVariableParamKey] = useState('');
    const [minValue, setMinValue] = useState(0);
    const [maxValue, setMaxValue] = useState(100);
    const [steps, setSteps] = useState(10);
    const [outputs, setOutputs] = useState([]);
    const [newOutputNodeId, setNewOutputNodeId] = useState('');
    const [newOutputKey, setNewOutputKey] = useState('duty');
    const [results, setResults] = useState(null);
    const [status, setStatus] = useState('idle');
    const [error, setError] = useState(null);
    const equipmentNodes = nodes.filter((n) => n.data.equipmentType in EquipmentType);
    const selectedNode = equipmentNodes.find((n) => n.id === variableNodeId);
    const paramKeys = selectedNode
        ? Object.keys(equipmentLibrary[selectedNode.data.equipmentType]?.parameters ?? {})
        : [];
    const addOutput = () => {
        if (!newOutputNodeId || !newOutputKey)
            return;
        const node = equipmentNodes.find((n) => n.id === newOutputNodeId);
        const label = `${node?.data.name ?? newOutputNodeId}.${newOutputKey}`;
        setOutputs([...outputs, { nodeId: newOutputNodeId, resultKey: newOutputKey, label }]);
    };
    const removeOutput = (index) => {
        setOutputs(outputs.filter((_, i) => i !== index));
    };
    const runSensitivity = async () => {
        if (!variableNodeId || !variableParamKey || outputs.length === 0)
            return;
        setStatus('running');
        setError(null);
        const simNodes = nodes.map((n) => ({
            id: n.id,
            type: n.data.equipmentType,
            name: n.data.name,
            parameters: { ...n.data.parameters },
            position: n.position,
        }));
        const simEdges = edges.map((e) => ({
            id: e.id,
            source: e.source,
            sourceHandle: e.sourceHandle ?? '',
            target: e.target,
            targetHandle: e.targetHandle ?? '',
            type: e.type ?? 'stream',
        }));
        try {
            const res = await fetch(`${API_BASE}/api/simulation/sensitivity`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_nodes: simNodes,
                    base_edges: simEdges,
                    property_package: propertyPackage,
                    simulation_basis: simulationBasis.compounds.length > 0 ? simulationBasis : undefined,
                    variable: {
                        node_id: variableNodeId,
                        parameter_key: variableParamKey,
                        min_value: minValue,
                        max_value: maxValue,
                        steps,
                    },
                    outputs: outputs.map((o) => ({
                        node_id: o.nodeId,
                        result_key: o.resultKey,
                    })),
                }),
            });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || `HTTP ${res.status}`);
            }
            const data = await res.json();
            setResults({
                variableValues: data.variable_values,
                outputValues: data.output_values,
                variableLabel: data.variable_label,
            });
            setStatus('completed');
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Sensitivity analysis failed');
            setStatus('error');
        }
    };
    // Build chart data
    const chartData = results
        ? results.variableValues.map((x, i) => {
            const point = { x };
            for (const [key, values] of Object.entries(results.outputValues)) {
                point[key] = values[i];
            }
            return point;
        })
        : [];
    if (!open)
        return null;
    return (_jsxs("div", { className: "absolute right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(LineChart, { size: 16, className: "text-blue-400" }), _jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Sensitivity Analysis" })] }), _jsx("button", { onClick: onClose, className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider", children: "Independent Variable" }), _jsxs("select", { value: variableNodeId, onChange: (e) => { setVariableNodeId(e.target.value); setVariableParamKey(''); }, className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500", children: [_jsx("option", { value: "", children: "Select equipment..." }), equipmentNodes.map((n) => (_jsxs("option", { value: n.id, children: [n.data.name, " (", n.data.equipmentType, ")"] }, n.id)))] }), variableNodeId && (_jsxs("select", { value: variableParamKey, onChange: (e) => setVariableParamKey(e.target.value), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500", children: [_jsx("option", { value: "", children: "Select parameter..." }), paramKeys.map((k) => (_jsx("option", { value: k, children: k }, k)))] })), _jsxs("div", { className: "flex gap-2", children: [_jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "block text-xs text-gray-500 mb-1", children: "Min" }), _jsx("input", { type: "number", value: minValue, onChange: (e) => setMinValue(Number(e.target.value)), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" })] }), _jsxs("div", { className: "flex-1", children: [_jsx("label", { className: "block text-xs text-gray-500 mb-1", children: "Max" }), _jsx("input", { type: "number", value: maxValue, onChange: (e) => setMaxValue(Number(e.target.value)), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" })] }), _jsxs("div", { className: "w-20", children: [_jsx("label", { className: "block text-xs text-gray-500 mb-1", children: "Steps" }), _jsx("input", { type: "number", value: steps, min: 2, max: 100, onChange: (e) => setSteps(Number(e.target.value)), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" })] })] })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider", children: "Tracked Outputs" }), _jsxs("div", { className: "flex gap-2 mb-2", children: [_jsxs("select", { value: newOutputNodeId, onChange: (e) => setNewOutputNodeId(e.target.value), className: "flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-xs rounded px-2 py-1.5 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500", children: [_jsx("option", { value: "", children: "Equipment..." }), equipmentNodes.map((n) => (_jsx("option", { value: n.id, children: n.data.name }, n.id)))] }), _jsx("select", { value: newOutputKey, onChange: (e) => setNewOutputKey(e.target.value), className: "flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-xs rounded px-2 py-1.5 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500", children: RESULT_KEYS.map((rk) => (_jsx("option", { value: rk.value, children: rk.label }, rk.value))) }), _jsx("button", { onClick: addOutput, className: "px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500", children: "Add" })] }), outputs.map((out, i) => (_jsxs("div", { className: "flex items-center justify-between px-2 py-1 bg-gray-50 dark:bg-gray-800/50 rounded mb-1 text-xs text-gray-700 dark:text-gray-300", children: [_jsx("span", { className: "truncate flex-1", children: out.label }), _jsx("button", { onClick: () => removeOutput(i), className: "ml-2 text-gray-400 hover:text-red-400", children: _jsx(X, { size: 12 }) })] }, i)))] }), _jsxs("button", { onClick: runSensitivity, disabled: status === 'running' || !variableNodeId || !variableParamKey || outputs.length === 0, className: `w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${status === 'running'
                            ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 cursor-not-allowed'
                            : 'bg-blue-600 text-white hover:bg-blue-500'}`, children: [status === 'running' ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), status === 'running' ? 'Running...' : 'Run Sensitivity'] }), error && (_jsx("div", { className: "text-xs text-red-400 bg-red-500/10 rounded p-2", children: error })), results && chartData.length > 0 && (_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider", children: "Results" }), _jsx("div", { className: "h-64 bg-gray-50 dark:bg-gray-800/50 rounded p-2", children: _jsx(ResponsiveContainer, { width: "100%", height: "100%", children: _jsxs(RechartsLineChart, { data: chartData, margin: { top: 5, right: 10, left: 10, bottom: 5 }, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#374151" }), _jsx(XAxis, { dataKey: "x", tick: { fontSize: 10, fill: '#9CA3AF' }, label: { value: results.variableLabel, position: 'insideBottom', offset: -2, fontSize: 10, fill: '#9CA3AF' } }), _jsx(YAxis, { tick: { fontSize: 10, fill: '#9CA3AF' } }), _jsx(Tooltip, { contentStyle: { backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '6px', fontSize: '11px' }, labelStyle: { color: '#9CA3AF' } }), _jsx(Legend, { wrapperStyle: { fontSize: '10px' } }), Object.keys(results.outputValues).map((key, i) => (_jsx(Line, { type: "monotone", dataKey: key, stroke: COLORS[i % COLORS.length], strokeWidth: 2, dot: { r: 2 }, name: key, connectNulls: true }, key)))] }) }) })] }))] })] }));
}
