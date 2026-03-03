import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { equipmentLibrary } from '../../lib/equipment-library';
const TARGET_PROPERTIES = [
    { value: 'temperature', label: 'Temperature (°C)' },
    { value: 'pressure', label: 'Pressure (kPa)' },
    { value: 'flowRate', label: 'Flow Rate (kg/s)' },
    { value: 'vapor_fraction', label: 'Vapor Fraction' },
];
export default function DesignSpecInspector({ parameters, onParamChange }) {
    const nodes = useFlowsheetStore((s) => s.nodes);
    const equipmentNodes = nodes.filter((n) => {
        const t = n.data?.equipmentType;
        return t && t !== 'DesignSpec' && t !== 'FeedStream' && t !== 'ProductStream';
    });
    const getParamKeys = (nid) => {
        const node = nodes.find((n) => n.id === nid);
        if (!node)
            return [];
        const eqType = node.data?.equipmentType;
        if (!eqType || !(eqType in equipmentLibrary))
            return [];
        return Object.keys(equipmentLibrary[eqType].parameters);
    };
    const getName = (nid) => {
        const node = nodes.find((n) => n.id === nid);
        return node?.data?.name || nid.slice(0, 8);
    };
    const inputClass = "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 focus:outline-none focus:border-blue-500";
    return (_jsxs("div", { className: "space-y-3", children: [_jsx("div", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider", children: "Target" }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Target Equipment" }), _jsxs("select", { value: parameters.targetStreamId || '', onChange: (e) => onParamChange('targetStreamId', e.target.value), className: inputClass, children: [_jsx("option", { value: "", children: "Select equipment" }), equipmentNodes.map((n) => (_jsxs("option", { value: n.id, children: [getName(n.id), " (", n.data?.equipmentType, ")"] }, n.id)))] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Target Property" }), _jsx("select", { value: parameters.targetProperty || 'temperature', onChange: (e) => onParamChange('targetProperty', e.target.value), className: inputClass, children: TARGET_PROPERTIES.map((p) => (_jsx("option", { value: p.value, children: p.label }, p.value))) })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Target Value" }), _jsx("input", { type: "number", value: parameters.targetValue ?? 0, onChange: (e) => onParamChange('targetValue', Number(e.target.value)), className: inputClass })] }), _jsx("div", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider pt-2", children: "Manipulated Variable" }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Manipulated Equipment" }), _jsxs("select", { value: parameters.manipulatedNodeId || '', onChange: (e) => onParamChange('manipulatedNodeId', e.target.value), className: inputClass, children: [_jsx("option", { value: "", children: "Select equipment" }), equipmentNodes.map((n) => (_jsxs("option", { value: n.id, children: [getName(n.id), " (", n.data?.equipmentType, ")"] }, n.id)))] })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Manipulated Parameter" }), _jsxs("select", { value: parameters.manipulatedParam || '', onChange: (e) => onParamChange('manipulatedParam', e.target.value), className: inputClass, children: [_jsx("option", { value: "", children: "Select parameter" }), parameters.manipulatedNodeId && getParamKeys(parameters.manipulatedNodeId).map((k) => (_jsx("option", { value: k, children: k }, k)))] })] }), _jsx("div", { className: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider pt-2", children: "Bounds" }), _jsxs("div", { className: "grid grid-cols-3 gap-2", children: [_jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Lower" }), _jsx("input", { type: "number", value: parameters.lowerBound ?? 0, onChange: (e) => onParamChange('lowerBound', Number(e.target.value)), className: inputClass })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Upper" }), _jsx("input", { type: "number", value: parameters.upperBound ?? 1000, onChange: (e) => onParamChange('upperBound', Number(e.target.value)), className: inputClass })] }), _jsxs("div", { children: [_jsx("label", { className: "text-[10px] text-gray-500", children: "Tolerance" }), _jsx("input", { type: "number", value: parameters.tolerance ?? 0.01, step: 0.001, onChange: (e) => onParamChange('tolerance', Number(e.target.value)), className: inputClass })] })] })] }));
}
