import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useRef, useCallback } from 'react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { useUnitStore } from '../../stores/unitStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { searchCompounds } from '../../lib/api-client';
import { EquipmentType, SimulationStatus } from '../../types';
import { X, Search, Trash2, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import DesignSpecInspector from './DesignSpecInspector';
const FEED_PARAM_KEYS = ['feedTemperature', 'feedPressure', 'feedFlowRate'];
export default function PropertyInspector() {
    const selectedNodeId = useFlowsheetStore((s) => s.selectedNodeId);
    const nodes = useFlowsheetStore((s) => s.nodes);
    const updateNodeData = useFlowsheetStore((s) => s.updateNodeData);
    const removeNode = useFlowsheetStore((s) => s.removeNode);
    const setSelectedNode = useFlowsheetStore((s) => s.setSelectedNode);
    const getUpstreamNodes = useFlowsheetStore((s) => s.getUpstreamNodes);
    const globalCompounds = useFlowsheetStore((s) => s.simulationBasis.compounds);
    const results = useSimulationStore((s) => s.results);
    const simStatus = useSimulationStore((s) => s.status);
    const node = nodes.find((n) => n.id === selectedNodeId);
    if (!node)
        return null;
    const def = equipmentLibrary[node.data.equipmentType];
    const upstreamNodes = getUpstreamNodes(node.id);
    const isFeedNode = upstreamNodes.length === 0 || node.data.equipmentType === EquipmentType.FeedStream;
    const isStreamNode = node.data.equipmentType === EquipmentType.FeedStream || node.data.equipmentType === EquipmentType.ProductStream;
    // Filter out feed params from regular display
    const regularParams = Object.entries(def.parameters).filter(([key]) => !FEED_PARAM_KEYS.includes(key));
    return (_jsxs("div", { className: "w-72 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col overflow-hidden", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Properties" }), _jsx("button", { onClick: () => setSelectedNode(null), className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Name" }), _jsx("input", { type: "text", value: node.data.name, onChange: (e) => updateNodeData(node.id, { name: e.target.value }), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Type" }), _jsx("div", { className: "text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5", children: def.label })] }), isFeedNode && (_jsx(FeedConditionsSection, { nodeId: node.id, parameters: node.data.parameters, paramDefs: def.parameters, updateNodeData: updateNodeData, globalCompounds: globalCompounds })), node.data.equipmentType === EquipmentType.DesignSpec && (_jsx("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-4", children: _jsx(DesignSpecInspector, { nodeId: node.id, parameters: node.data.parameters, onParamChange: (key, value) => updateNodeData(node.id, {
                                parameters: { ...node.data.parameters, [key]: value },
                            }) }) })), _jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-4", children: [_jsx("h3", { className: "text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3", children: "Parameters" }), _jsx("div", { className: "space-y-3", children: regularParams.map(([key, paramDef]) => (_jsxs("div", { children: [_jsxs("label", { className: "flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1", children: [_jsx("span", { children: paramDef.label }), paramDef.unit && (_jsx("span", { className: "text-gray-500 dark:text-gray-500", children: paramDef.unit }))] }), paramDef.type === 'boolean' ? (_jsx("button", { onClick: () => updateNodeData(node.id, {
                                                parameters: {
                                                    ...node.data.parameters,
                                                    [key]: !node.data.parameters[key],
                                                },
                                            }), className: `w-full text-left px-3 py-1.5 rounded text-sm border ${node.data.parameters[key]
                                                ? 'bg-blue-500/20 border-blue-500 text-blue-300'
                                                : 'bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300'}`, children: node.data.parameters[key] ? 'Enabled' : 'Disabled' })) : paramDef.type === 'number' ? (_jsx("input", { type: "number", value: node.data.parameters[key] !== undefined ? node.data.parameters[key] : '', placeholder: "Not set", min: paramDef.min, max: paramDef.max, onChange: (e) => updateNodeData(node.id, {
                                                parameters: {
                                                    ...node.data.parameters,
                                                    [key]: e.target.value === '' ? undefined : parseFloat(e.target.value) || 0,
                                                },
                                            }), onBlur: (e) => {
                                                const val = parseFloat(e.target.value);
                                                if (isNaN(val))
                                                    return;
                                                let clamped = val;
                                                if (paramDef.min !== undefined)
                                                    clamped = Math.max(paramDef.min, clamped);
                                                if (paramDef.max !== undefined)
                                                    clamped = Math.min(paramDef.max, clamped);
                                                if (clamped !== val) {
                                                    updateNodeData(node.id, {
                                                        parameters: { ...node.data.parameters, [key]: clamped },
                                                    });
                                                }
                                            }, className: `w-full bg-gray-100 dark:bg-gray-800 border rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500 placeholder-gray-400 dark:placeholder-gray-600 ${(() => {
                                                const v = node.data.parameters[key];
                                                if (v === undefined || v === '')
                                                    return 'border-gray-300 dark:border-gray-700';
                                                const n = Number(v);
                                                if (isNaN(n))
                                                    return 'border-gray-300 dark:border-gray-700';
                                                if ((paramDef.min !== undefined && n < paramDef.min) || (paramDef.max !== undefined && n > paramDef.max))
                                                    return 'border-red-500 ring-1 ring-red-500';
                                                return 'border-gray-300 dark:border-gray-700';
                                            })()}` })) : (_jsx("input", { type: "text", value: node.data.parameters[key], onChange: (e) => updateNodeData(node.id, {
                                                parameters: {
                                                    ...node.data.parameters,
                                                    [key]: e.target.value,
                                                },
                                            }), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" }))] }, key))) })] }), isStreamNode && simStatus === SimulationStatus.Completed && results && (_jsx(SimResultsSection, { nodeId: node.id, equipmentType: node.data.equipmentType, results: results })), _jsx("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-4", children: _jsx("button", { onClick: () => {
                                removeNode(node.id);
                                setSelectedNode(null);
                            }, className: "w-full px-3 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded text-sm hover:bg-red-500/20 transition-colors", children: "Delete Equipment" }) })] })] }));
}
// ── Simulation Results Section for FeedStream/ProductStream ──
function fmt(v, decimals = 4) {
    if (v == null || isNaN(v))
        return '-';
    return v.toFixed(decimals);
}
function SimResultsSection({ nodeId, equipmentType, results }) {
    const [compExpanded, setCompExpanded] = useState(false);
    const us = useUnitStore((s) => s.unitSystem);
    const cv = us.fromSI;
    const un = us.units;
    const eqResult = results.equipmentResults[nodeId];
    if (!eqResult)
        return null;
    // Engine returns camelCase keys: outletTemperature, outletPressure, massFlow, vaporFraction
    // Also has nested inlet_streams/outlet_streams with standard keys
    const streamKey = equipmentType === EquipmentType.FeedStream ? 'outlet_streams' : 'inlet_streams';
    const portKey = equipmentType === EquipmentType.FeedStream ? 'out-1' : 'in-1';
    const nested = eqResult[streamKey]?.[portKey];
    // Prefer nested stream dict (has standard keys), fall back to top-level camelCase
    const temp = (nested?.temperature ?? eqResult.outletTemperature);
    const pres = (nested?.pressure ?? eqResult.outletPressure);
    const flow = (nested?.flowRate ?? eqResult.massFlow);
    const vf = (nested?.vapor_fraction ?? eqResult.vaporFraction);
    const enthalpy = (nested?.enthalpy ?? eqResult.enthalpy);
    const mw = (nested?.molecular_weight ?? eqResult.molecular_weight);
    const molarFlow = (nested?.molar_flow ?? eqResult.molar_flow);
    const massFracs = (nested?.mass_fractions ?? eqResult.mass_fractions);
    const compMolarFlows = (nested?.component_molar_flows ?? eqResult.component_molar_flows);
    const compMassFlows = (nested?.component_mass_flows ?? eqResult.component_mass_flows);
    const hasAnyData = temp != null || pres != null || flow != null;
    if (!hasAnyData)
        return null;
    const hasComponents = compMolarFlows && Object.keys(compMolarFlows).length > 0;
    return (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-4", children: [_jsx("h3", { className: "text-xs font-semibold text-green-400 uppercase tracking-wider mb-3", children: equipmentType === EquipmentType.FeedStream ? 'Outlet Conditions' : 'Inlet Conditions' }), _jsxs("div", { className: "space-y-1.5", children: [temp != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Temperature" }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [fmt(cv.temperature(temp), 2), " ", _jsx("span", { className: "text-gray-500 text-[10px]", children: un.temperature })] })] })), pres != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Pressure" }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [fmt(cv.pressure(pres), 2), " ", _jsx("span", { className: "text-gray-500 text-[10px]", children: un.pressure })] })] })), flow != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Mass Flow" }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [fmt(cv.massFlow(flow), 4), " ", _jsx("span", { className: "text-gray-500 text-[10px]", children: un.massFlow })] })] })), vf != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Vapor Fraction" }), _jsx("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: fmt(vf, 4) })] })), enthalpy != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Enthalpy" }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [fmt(cv.enthalpy(enthalpy), 2), " ", _jsx("span", { className: "text-gray-500 text-[10px]", children: un.enthalpy })] })] })), mw != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "MW (mix)" }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [fmt(mw, 2), " ", _jsx("span", { className: "text-gray-500 text-[10px]", children: "g/mol" })] })] })), molarFlow != null && (_jsxs("div", { className: "flex justify-between text-xs", children: [_jsx("span", { className: "text-gray-500 dark:text-gray-400", children: "Molar Flow" }), _jsxs("span", { className: "text-gray-900 dark:text-gray-100 font-mono", children: [fmt(cv.molarFlow(molarFlow), 4), " ", _jsx("span", { className: "text-gray-500 text-[10px]", children: un.molarFlow })] })] }))] }), hasComponents && (_jsxs("div", { className: "mt-3 pt-2 border-t border-gray-100 dark:border-gray-800/50", children: [_jsxs("button", { onClick: () => setCompExpanded(!compExpanded), className: "flex items-center gap-1 text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2 hover:text-blue-300 transition-colors w-full", children: [compExpanded ? _jsx(ChevronDown, { size: 12 }) : _jsx(ChevronRight, { size: 12 }), "Component Properties"] }), compExpanded && (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full text-[10px]", children: [_jsx("thead", { children: _jsxs("tr", { className: "text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800", children: [_jsx("th", { className: "text-left py-1 pr-1", children: "Component" }), _jsx("th", { className: "text-right py-1 px-1", children: "Mass Frac" }), _jsx("th", { className: "text-right py-1 px-1", children: "mol/s" }), _jsx("th", { className: "text-right py-1 pl-1", children: "kg/s" })] }) }), _jsx("tbody", { children: Object.keys(compMolarFlows).map((name) => (_jsxs("tr", { className: "border-b border-gray-100 dark:border-gray-800/50", children: [_jsx("td", { className: "py-1 pr-1 text-gray-600 dark:text-gray-400 truncate max-w-[70px]", title: name, children: name }), _jsx("td", { className: "py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100", children: fmt(massFracs?.[name], 4) }), _jsx("td", { className: "py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100", children: fmt(compMolarFlows?.[name], 4) }), _jsx("td", { className: "py-1 pl-1 text-right font-mono text-gray-900 dark:text-gray-100", children: fmt(compMassFlows?.[name], 4) })] }, name))) })] }) }))] }))] }));
}
function FeedConditionsSection({ nodeId, parameters, paramDefs, updateNodeData, globalCompounds }) {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showResults, setShowResults] = useState(false);
    const searchTimeout = useRef(null);
    const searchContainerRef = useRef(null);
    // Parse feedComposition from parameters
    const feedComposition = (() => {
        const raw = parameters.feedComposition;
        if (!raw)
            return {};
        if (typeof raw === 'string') {
            try {
                return JSON.parse(raw);
            }
            catch {
                return {};
            }
        }
        if (typeof raw === 'object')
            return raw;
        return {};
    })();
    const setComposition = useCallback((comp) => {
        updateNodeData(nodeId, {
            parameters: {
                ...parameters,
                feedComposition: JSON.stringify(comp),
            },
        });
    }, [nodeId, parameters, updateNodeData]);
    // Debounced compound search
    useEffect(() => {
        if (searchTimeout.current)
            clearTimeout(searchTimeout.current);
        if (searchQuery.length < 2) {
            setSearchResults([]);
            setShowResults(false);
            return;
        }
        searchTimeout.current = setTimeout(async () => {
            setIsSearching(true);
            try {
                let results = await searchCompounds(searchQuery);
                // Filter by global compound list if defined
                if (globalCompounds && globalCompounds.length > 0) {
                    results = results.filter((c) => globalCompounds.includes(c.name));
                }
                setSearchResults(results);
                setShowResults(true);
            }
            catch {
                setSearchResults([]);
            }
            finally {
                setIsSearching(false);
            }
        }, 300);
        return () => {
            if (searchTimeout.current)
                clearTimeout(searchTimeout.current);
        };
    }, [searchQuery]);
    // Close search dropdown on outside click
    useEffect(() => {
        const handleClick = (e) => {
            if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
                setShowResults(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);
    const addCompound = (compound) => {
        if (feedComposition[compound.name] !== undefined)
            return;
        const newComp = { ...feedComposition, [compound.name]: 0 };
        setComposition(newComp);
        setSearchQuery('');
        setShowResults(false);
    };
    const removeCompound = (name) => {
        const newComp = { ...feedComposition };
        delete newComp[name];
        setComposition(newComp);
    };
    const updateFraction = (name, value) => {
        setComposition({ ...feedComposition, [name]: value });
    };
    const autoNormalize = () => {
        const entries = Object.entries(feedComposition);
        if (entries.length === 0)
            return;
        const total = entries.reduce((sum, [, v]) => sum + v, 0);
        if (total === 0) {
            const equal = 1 / entries.length;
            setComposition(Object.fromEntries(entries.map(([k]) => [k, equal])));
        }
        else {
            setComposition(Object.fromEntries(entries.map(([k, v]) => [k, v / total])));
        }
    };
    const total = Object.values(feedComposition).reduce((s, v) => s + v, 0);
    return (_jsxs("div", { className: "border-t border-gray-200 dark:border-gray-800 pt-4", children: [_jsx("h3", { className: "text-xs font-semibold text-blue-400 uppercase tracking-wider mb-3", children: "Feed Conditions" }), _jsx("div", { className: "space-y-3 mb-4", children: FEED_PARAM_KEYS.map((key) => {
                    const paramDef = paramDefs[key];
                    if (!paramDef)
                        return null;
                    return (_jsxs("div", { children: [_jsxs("label", { className: "flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1", children: [_jsx("span", { children: paramDef.label }), paramDef.unit && _jsx("span", { className: "text-gray-500", children: paramDef.unit })] }), _jsx("input", { type: "number", value: parameters[key], min: paramDef.min, max: paramDef.max, onChange: (e) => updateNodeData(nodeId, {
                                    parameters: {
                                        ...parameters,
                                        [key]: parseFloat(e.target.value) || 0,
                                    },
                                }), className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" })] }, key));
                }) }), _jsxs("div", { className: "mb-3", ref: searchContainerRef, children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Add Compound" }), _jsxs("div", { className: "relative", children: [_jsx(Search, { size: 12, className: "absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" }), _jsx("input", { type: "text", value: searchQuery, onChange: (e) => setSearchQuery(e.target.value), placeholder: "Search compounds...", className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded pl-7 pr-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" }), isSearching && (_jsx("div", { className: "absolute right-2.5 top-1/2 -translate-y-1/2", children: _jsx("div", { className: "w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" }) }))] }), showResults && searchResults.length > 0 && (_jsx("div", { className: "mt-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded max-h-40 overflow-y-auto custom-scrollbar", children: searchResults.map((compound) => (_jsxs("button", { onClick: () => addCompound(compound), disabled: feedComposition[compound.name] !== undefined, className: `w-full text-left px-3 py-1.5 text-xs hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center justify-between ${feedComposition[compound.name] !== undefined
                                ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                                : 'text-gray-700 dark:text-gray-300'}`, children: [_jsx("span", { children: compound.name }), _jsx("span", { className: "text-gray-500", children: compound.formula })] }, compound.cas || compound.name))) })), showResults && searchResults.length === 0 && searchQuery.length >= 2 && !isSearching && (_jsx("div", { className: "mt-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-2 text-xs text-gray-500", children: "No compounds found" }))] }), Object.keys(feedComposition).length > 0 && (_jsxs("div", { className: "mb-3", children: [_jsxs("div", { className: "flex items-center justify-between mb-2", children: [_jsx("label", { className: "text-xs text-gray-500 dark:text-gray-400", children: "Composition (mole fraction)" }), _jsxs("button", { onClick: autoNormalize, title: "Auto-normalize to 1.0", className: "flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors", children: [_jsx(RefreshCw, { size: 10 }), "Normalize"] })] }), _jsx("div", { className: "space-y-1.5", children: Object.entries(feedComposition).map(([name, fraction]) => (_jsxs("div", { className: "flex items-center gap-1.5", children: [_jsx("span", { className: "text-xs text-gray-700 dark:text-gray-300 flex-1 truncate", title: name, children: name }), _jsx("input", { type: "number", value: fraction, min: 0, max: 1, step: 0.01, onChange: (e) => updateFraction(name, Math.max(0, parseFloat(e.target.value) || 0)), className: "w-20 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-xs text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" }), _jsx("button", { onClick: () => removeCompound(name), className: "p-0.5 text-gray-500 hover:text-red-400 transition-colors", children: _jsx(Trash2, { size: 12 }) })] }, name))) }), _jsxs("div", { className: `text-xs mt-1.5 ${Math.abs(total - 1) < 0.001 ? 'text-green-400' : 'text-yellow-400'}`, children: ["Total: ", total.toFixed(4), Math.abs(total - 1) >= 0.001 && ' (should be 1.0)'] })] }))] }));
}
