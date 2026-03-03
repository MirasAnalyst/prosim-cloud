import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { useUnitStore } from '../../stores/unitStore';
import { SimulationStatus } from '../../types';
import { X, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';
function fmt(v, decimals = 4) {
    if (v == null || isNaN(v))
        return '-';
    return v.toFixed(decimals);
}
function fmtSci(v) {
    if (v == null || isNaN(v))
        return '-';
    if (Math.abs(v) < 0.001 || Math.abs(v) > 1e6)
        return v.toExponential(3);
    return v.toFixed(4);
}
function TransportPropertiesSection({ conditions }) {
    const [expanded, setExpanded] = useState(false);
    const hasAny = conditions.density != null ||
        conditions.viscosity != null ||
        conditions.thermal_conductivity != null ||
        conditions.surface_tension != null ||
        conditions.Cp_mass != null ||
        conditions.Cv_mass != null ||
        conditions.Z_factor != null ||
        conditions.volumetric_flow != null;
    if (!hasAny)
        return null;
    return (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-3", children: [_jsxs("button", { onClick: () => setExpanded(!expanded), className: "flex items-center gap-1 text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2 hover:text-purple-300 transition-colors w-full", children: [expanded ? _jsx(ChevronDown, { size: 12 }) : _jsx(ChevronRight, { size: 12 }), "Transport Properties"] }), expanded && (_jsxs("div", { className: "space-y-1.5", children: [conditions.density != null && (_jsx(PropertyRow, { label: "Density", value: fmt(conditions.density, 2), unit: "kg/m\u00B3" })), conditions.viscosity != null && (_jsx(PropertyRow, { label: "Viscosity", value: fmtSci(conditions.viscosity), unit: "Pa\u00B7s" })), conditions.thermal_conductivity != null && (_jsx(PropertyRow, { label: "Thermal Cond.", value: fmtSci(conditions.thermal_conductivity), unit: "W/m\u00B7K" })), conditions.surface_tension != null && (_jsx(PropertyRow, { label: "Surface Tension", value: fmtSci(conditions.surface_tension), unit: "N/m" })), conditions.Cp_mass != null && (_jsx(PropertyRow, { label: "Cp", value: fmt(conditions.Cp_mass, 2), unit: "J/kg\u00B7K" })), conditions.Cv_mass != null && (_jsx(PropertyRow, { label: "Cv", value: fmt(conditions.Cv_mass, 2), unit: "J/kg\u00B7K" })), conditions.Z_factor != null && (_jsx(PropertyRow, { label: "Z Factor", value: fmt(conditions.Z_factor, 4), unit: "" })), conditions.volumetric_flow != null && (_jsx(PropertyRow, { label: "Vol. Flow", value: fmtSci(conditions.volumetric_flow), unit: "m\u00B3/s" }))] }))] }));
}
function PhasePropertiesSection({ conditions }) {
    const [expanded, setExpanded] = useState(false);
    const pp = conditions.phase_properties;
    if (!pp)
        return null;
    const VF = conditions.vapor_fraction ?? 0;
    const hasLiquid = VF < 1.0 && pp.liquid;
    const hasVapor = VF > 0.0 && pp.vapor;
    if (!hasLiquid && !hasVapor)
        return null;
    return (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-3", children: [_jsxs("button", { onClick: () => setExpanded(!expanded), className: "flex items-center gap-1 text-xs font-semibold text-green-400 uppercase tracking-wider mb-2 hover:text-green-300 transition-colors w-full", children: [expanded ? _jsx(ChevronDown, { size: 12 }) : _jsx(ChevronRight, { size: 12 }), "Phase Properties"] }), expanded && (_jsxs("div", { className: "space-y-3", children: [hasVapor && pp.vapor && (_jsx(PhaseDetail, { label: "Vapor Phase", phase: pp.vapor })), hasLiquid && pp.liquid && (_jsx(PhaseDetail, { label: "Liquid Phase", phase: pp.liquid }))] }))] }));
}
function PhaseDetail({ label, phase }) {
    const [compExpanded, setCompExpanded] = useState(false);
    return (_jsxs("div", { className: "bg-gray-50 dark:bg-gray-800/50 rounded p-2", children: [_jsx("h4", { className: "text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1.5", children: label }), _jsxs("div", { className: "space-y-1", children: [phase.density != null && (_jsx(PropertyRow, { label: "Density", value: fmt(phase.density, 2), unit: "kg/m\u00B3" })), phase.viscosity != null && (_jsx(PropertyRow, { label: "Viscosity", value: fmtSci(phase.viscosity), unit: "Pa\u00B7s" })), phase.thermal_conductivity != null && (_jsx(PropertyRow, { label: "Thermal Cond.", value: fmtSci(phase.thermal_conductivity), unit: "W/m\u00B7K" })), phase.Cp != null && (_jsx(PropertyRow, { label: "Cp", value: fmt(phase.Cp, 2), unit: "J/mol\u00B7K" })), phase.Cv != null && (_jsx(PropertyRow, { label: "Cv", value: fmt(phase.Cv, 2), unit: "J/mol\u00B7K" })), phase.enthalpy != null && (_jsx(PropertyRow, { label: "Enthalpy", value: fmt(phase.enthalpy, 2), unit: "J/mol" })), phase.entropy != null && (_jsx(PropertyRow, { label: "Entropy", value: fmt(phase.entropy, 4), unit: "J/mol\u00B7K" })), phase.Z != null && (_jsx(PropertyRow, { label: "Z Factor", value: fmt(phase.Z, 4), unit: "" }))] }), phase.composition && Object.keys(phase.composition).length > 0 && (_jsxs("div", { className: "mt-1.5", children: [_jsxs("button", { onClick: () => setCompExpanded(!compExpanded), className: "flex items-center gap-1 text-[10px] text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300", children: [compExpanded ? _jsx(ChevronDown, { size: 10 }) : _jsx(ChevronRight, { size: 10 }), "Composition"] }), compExpanded && (_jsx("div", { className: "mt-1 space-y-0.5", children: Object.entries(phase.composition).map(([name, z]) => (_jsxs("div", { className: "flex justify-between text-[10px]", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400 truncate mr-2", children: name }), _jsx("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: fmt(z, 6) })] }, name))) }))] }))] }));
}
function StreamPropertiesDisplay({ conditions }) {
    const [compExpanded, setCompExpanded] = useState(true);
    const us = useUnitStore((s) => s.unitSystem);
    const cv = us.fromSI;
    const un = us.units;
    const hasComponents = conditions.component_molar_flows &&
        Object.keys(conditions.component_molar_flows).length > 0;
    return (_jsxs("div", { className: "space-y-3", children: [_jsxs("div", { children: [_jsx("h3", { className: "text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2", children: "Conditions" }), _jsxs("div", { className: "space-y-1.5", children: [_jsx(PropertyRow, { label: "Temperature", value: fmt(cv.temperature(conditions.temperature), 2), unit: un.temperature }), _jsx(PropertyRow, { label: "Pressure", value: fmt(cv.pressure(conditions.pressure), 2), unit: un.pressure }), _jsx(PropertyRow, { label: "Mass Flow", value: fmt(cv.massFlow(conditions.flowRate), 4), unit: un.massFlow }), _jsx(PropertyRow, { label: "Vapor Fraction", value: fmt(conditions.vapor_fraction, 4), unit: "" }), conditions.enthalpy != null && (_jsx(PropertyRow, { label: "Enthalpy", value: fmt(cv.enthalpy(conditions.enthalpy), 2), unit: un.enthalpy })), conditions.molecular_weight != null && (_jsx(PropertyRow, { label: "MW (mix)", value: fmt(conditions.molecular_weight, 2), unit: "g/mol" })), conditions.molar_flow != null && (_jsx(PropertyRow, { label: "Molar Flow", value: fmt(cv.molarFlow(conditions.molar_flow), 4), unit: un.molarFlow }))] })] }), _jsx(TransportPropertiesSection, { conditions: conditions }), _jsx(PhasePropertiesSection, { conditions: conditions }), conditions.composition && Object.keys(conditions.composition).length > 0 && (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-3", children: [_jsx("h3", { className: "text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2", children: "Composition (Mole Fraction)" }), _jsx("div", { className: "space-y-1", children: Object.entries(conditions.composition).map(([name, z]) => (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-600 dark:text-gray-400 truncate mr-2", children: name }), _jsx("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: fmt(z, 6) })] }, name))) })] })), hasComponents && (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-3", children: [_jsxs("button", { onClick: () => setCompExpanded(!compExpanded), className: "flex items-center gap-1 text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2 hover:text-blue-300 transition-colors w-full", children: [compExpanded ? _jsx(ChevronDown, { size: 12 }) : _jsx(ChevronRight, { size: 12 }), "Component Properties"] }), compExpanded && (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full text-[10px]", children: [_jsx("thead", { children: _jsxs("tr", { className: "text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800", children: [_jsx("th", { className: "text-left py-1 pr-2", children: "Component" }), _jsx("th", { className: "text-right py-1 px-1", children: "Mass Frac" }), _jsx("th", { className: "text-right py-1 px-1", children: "Molar Flow" }), _jsx("th", { className: "text-right py-1 pl-1", children: "Mass Flow" })] }) }), _jsx("tbody", { children: Object.keys(conditions.component_molar_flows).map((name) => (_jsxs("tr", { className: "border-b border-gray-100 dark:border-gray-800/50", children: [_jsx("td", { className: "py-1 pr-2 text-gray-600 dark:text-gray-400 truncate max-w-[80px]", title: name, children: name }), _jsx("td", { className: "py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100", children: fmt(conditions.mass_fractions?.[name], 4) }), _jsx("td", { className: "py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100", children: fmt(conditions.component_molar_flows?.[name] != null ? cv.molarFlow(conditions.component_molar_flows[name]) : undefined, 4) }), _jsx("td", { className: "py-1 pl-1 text-right font-mono text-gray-900 dark:text-gray-100", children: fmt(conditions.component_mass_flows?.[name] != null ? cv.massFlow(conditions.component_mass_flows[name]) : undefined, 4) })] }, name))) }), _jsx("tfoot", { children: _jsxs("tr", { className: "text-gray-500 dark:text-gray-400 font-semibold", children: [_jsx("td", { className: "py-1 pr-2", children: "Units" }), _jsx("td", { className: "py-1 px-1 text-right", children: "-" }), _jsx("td", { className: "py-1 px-1 text-right", children: un.molarFlow }), _jsx("td", { className: "py-1 pl-1 text-right", children: un.massFlow })] }) })] }) }))] }))] }));
}
function PropertyRow({ label, value, unit }) {
    return (_jsxs("div", { className: "flex items-center justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: label }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [value, " ", _jsx("span", { className: "text-gray-500 dark:text-gray-500 text-[10px]", children: unit })] })] }));
}
export default function StreamInspector() {
    const selectedEdgeId = useFlowsheetStore((s) => s.selectedEdgeId);
    const edges = useFlowsheetStore((s) => s.edges);
    const nodes = useFlowsheetStore((s) => s.nodes);
    const setSelectedEdge = useFlowsheetStore((s) => s.setSelectedEdge);
    const results = useSimulationStore((s) => s.results);
    const status = useSimulationStore((s) => s.status);
    if (!selectedEdgeId)
        return null;
    const edge = edges.find((e) => e.id === selectedEdgeId);
    if (!edge)
        return null;
    // Find source and target node names
    const sourceNode = nodes.find((n) => n.id === edge.source);
    const targetNode = nodes.find((n) => n.id === edge.target);
    const streamName = `${sourceNode?.data.name ?? 'Source'} → ${targetNode?.data.name ?? 'Target'}`;
    const streamResult = status === SimulationStatus.Completed && results?.streamResults
        ? results.streamResults[selectedEdgeId]
        : null;
    return (_jsxs("div", { className: "w-72 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col overflow-hidden", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Stream" }), _jsx("button", { onClick: () => setSelectedEdge(null), className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Connection" }), _jsx("div", { className: "text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5", children: streamName })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Type" }), _jsx("div", { className: "text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5", children: edge.type === 'energy-stream' ? 'Energy Stream' : 'Material Stream' })] }), streamResult ? (_jsx("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-3", children: _jsx(StreamPropertiesDisplay, { conditions: streamResult }) })) : (_jsx("div", { className: "text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center", children: status === SimulationStatus.Completed
                            ? 'No results for this stream'
                            : 'Run simulation to see stream properties' }))] })] }));
}
