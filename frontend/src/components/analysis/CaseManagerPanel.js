import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { X, Save, Trash2, Upload, FolderOpen, GitCompare, Loader2 } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
export default function CaseManagerPanel({ open, onClose }) {
    const nodes = useFlowsheetStore((s) => s.nodes);
    const edges = useFlowsheetStore((s) => s.edges);
    const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
    const currentProjectId = useFlowsheetStore((s) => s.currentProjectId);
    const propertyPackage = useSimulationStore((s) => s.propertyPackage);
    const lastResults = useSimulationStore((s) => s.results);
    const [cases, setCases] = useState([]);
    const [caseName, setCaseName] = useState('');
    const [caseDesc, setCaseDesc] = useState('');
    const [loading, setLoading] = useState(false);
    const [selectedIds, setSelectedIds] = useState([]);
    const [compareResult, setCompareResult] = useState(null);
    const [error, setError] = useState(null);
    const fetchCases = async () => {
        if (!currentProjectId)
            return;
        try {
            const res = await fetch(`/api/projects/${currentProjectId}/cases`);
            if (res.ok) {
                setCases(await res.json());
            }
        }
        catch {
            // ignore
        }
    };
    useEffect(() => {
        if (open && currentProjectId) {
            fetchCases();
        }
    }, [open, currentProjectId]);
    const saveCase = async () => {
        if (!currentProjectId || !caseName.trim())
            return;
        setLoading(true);
        setError(null);
        try {
            const simNodes = nodes.map((n) => ({
                id: n.id,
                type: n.type,
                data: n.data,
                position: n.position,
            }));
            const simEdges = edges.map((e) => ({
                id: e.id,
                source: e.source,
                sourceHandle: e.sourceHandle ?? '',
                target: e.target,
                targetHandle: e.targetHandle ?? '',
                type: e.type,
            }));
            const res = await fetch(`/api/projects/${currentProjectId}/cases`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: caseName.trim(),
                    description: caseDesc.trim() || null,
                    nodes: simNodes,
                    edges: simEdges,
                    simulation_basis: simulationBasis,
                    property_package: propertyPackage,
                    results: lastResults,
                }),
            });
            if (!res.ok)
                throw new Error(`HTTP ${res.status}`);
            setCaseName('');
            setCaseDesc('');
            await fetchCases();
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save case');
        }
        finally {
            setLoading(false);
        }
    };
    const loadCase = async (caseId) => {
        if (!currentProjectId)
            return;
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`/api/projects/${currentProjectId}/cases/${caseId}/load`, {
                method: 'POST',
            });
            if (!res.ok)
                throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            // Apply to flowsheet store — use setState for nodes/edges since there's no setter method
            useFlowsheetStore.setState({
                nodes: data.nodes,
                edges: data.edges,
            });
            if (data.simulation_basis) {
                useFlowsheetStore.getState().setSimulationBasis(data.simulation_basis);
            }
            if (data.property_package) {
                useSimulationStore.getState().setPropertyPackage(data.property_package);
            }
            if (data.results) {
                useSimulationStore.setState({ results: data.results });
            }
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load case');
        }
        finally {
            setLoading(false);
        }
    };
    const deleteCase = async (caseId) => {
        if (!currentProjectId)
            return;
        try {
            await fetch(`/api/projects/${currentProjectId}/cases/${caseId}`, {
                method: 'DELETE',
            });
            setSelectedIds(selectedIds.filter((id) => id !== caseId));
            await fetchCases();
        }
        catch {
            // ignore
        }
    };
    const toggleSelect = (caseId) => {
        setSelectedIds((prev) => prev.includes(caseId) ? prev.filter((id) => id !== caseId) : [...prev, caseId]);
        setCompareResult(null);
    };
    const compareCases = async () => {
        if (!currentProjectId || selectedIds.length < 2)
            return;
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`/api/projects/${currentProjectId}/cases/compare`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ case_ids: selectedIds }),
            });
            if (!res.ok)
                throw new Error(`HTTP ${res.status}`);
            setCompareResult(await res.json());
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to compare cases');
        }
        finally {
            setLoading(false);
        }
    };
    if (!open)
        return null;
    return (_jsxs("div", { className: "absolute right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(FolderOpen, { size: 16, className: "text-blue-400" }), _jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200", children: "Case Studies" })] }), _jsx("button", { onClick: onClose, className: "p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "flex-1 overflow-y-auto p-4 space-y-4", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider", children: "Save Current State" }), _jsx("input", { type: "text", value: caseName, onChange: (e) => setCaseName(e.target.value), placeholder: "Case name...", className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500" }), _jsx("input", { type: "text", value: caseDesc, onChange: (e) => setCaseDesc(e.target.value), placeholder: "Description (optional)...", className: "w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500" }), _jsxs("button", { onClick: saveCase, disabled: !caseName.trim() || loading, className: "w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed", children: [loading ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Save, { size: 14 }), "Save Case"] })] }), error && (_jsx("div", { className: "text-xs text-red-400 bg-red-500/10 rounded p-2", children: error })), _jsxs("div", { children: [_jsxs("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider", children: ["Saved Cases (", cases.length, ")"] }), cases.length > 0 ? (_jsx("div", { className: "space-y-2", children: cases.map((c) => (_jsxs("div", { className: `px-3 py-2 rounded border text-sm ${selectedIds.includes(c.id)
                                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                                        : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'}`, children: [_jsxs("div", { className: "flex items-center justify-between mb-1", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("input", { type: "checkbox", checked: selectedIds.includes(c.id), onChange: () => toggleSelect(c.id), className: "rounded border-gray-300 dark:border-gray-600" }), _jsx("span", { className: "font-medium text-gray-800 dark:text-gray-200 truncate", children: c.name })] }), _jsxs("div", { className: "flex items-center gap-1", children: [_jsx("button", { onClick: () => loadCase(c.id), title: "Load case", className: "p-1 text-gray-400 hover:text-blue-400 transition-colors", children: _jsx(Upload, { size: 12 }) }), _jsx("button", { onClick: () => deleteCase(c.id), title: "Delete case", className: "p-1 text-gray-400 hover:text-red-400 transition-colors", children: _jsx(Trash2, { size: 12 }) })] })] }), _jsxs("div", { className: "text-xs text-gray-500 dark:text-gray-400 flex gap-3", children: [_jsx("span", { children: c.property_package }), _jsx("span", { children: new Date(c.created_at).toLocaleDateString() })] }), c.description && (_jsx("div", { className: "text-xs text-gray-500 dark:text-gray-400 mt-1 truncate", children: c.description }))] }, c.id))) })) : (_jsx("div", { className: "text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center", children: "No saved cases. Save the current flowsheet state above." }))] }), selectedIds.length >= 2 && (_jsxs("button", { onClick: compareCases, disabled: loading || selectedIds.length > 3, className: "w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-500 disabled:opacity-50", children: [_jsx(GitCompare, { size: 14 }), "Compare ", selectedIds.length, " Cases"] })), compareResult && (_jsxs("div", { children: [_jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider", children: "Comparison" }), _jsxs("div", { className: "bg-gray-50 dark:bg-gray-800/50 rounded p-3 text-xs space-y-2", children: [_jsxs("div", { className: "grid gap-1", style: { gridTemplateColumns: `100px repeat(${compareResult.cases.length}, 1fr)` }, children: [_jsx("div", { className: "font-semibold text-gray-500 dark:text-gray-400", children: "Metric" }), compareResult.cases.map((c) => (_jsx("div", { className: "font-semibold text-gray-700 dark:text-gray-300 truncate", children: c.name }, c.id)))] }), _jsxs("div", { className: "grid gap-1", style: { gridTemplateColumns: `100px repeat(${compareResult.cases.length}, 1fr)` }, children: [_jsx("div", { className: "text-gray-500", children: "Prop. Pkg" }), compareResult.diffs.property_packages.map((pp, i) => (_jsx("div", { className: "text-gray-700 dark:text-gray-300", children: pp }, i)))] }), _jsxs("div", { className: "grid gap-1", style: { gridTemplateColumns: `100px repeat(${compareResult.cases.length}, 1fr)` }, children: [_jsx("div", { className: "text-gray-500", children: "Equipment" }), compareResult.diffs.node_counts.map((n, i) => (_jsx("div", { className: "text-gray-700 dark:text-gray-300", children: n }, i)))] }), Object.entries(compareResult.diffs.equipment_results).map(([eqId, results]) => (_jsxs("div", { children: [_jsx("div", { className: "font-medium text-gray-600 dark:text-gray-400 mt-1 mb-0.5 truncate", children: eqId }), results.length > 0 && Object.keys(results[0] || {}).filter((k) => typeof results[0][k] === 'number').slice(0, 5).map((metric) => (_jsxs("div", { className: "grid gap-1", style: { gridTemplateColumns: `100px repeat(${results.length}, 1fr)` }, children: [_jsx("div", { className: "text-gray-500 truncate", children: metric }), results.map((r, i) => {
                                                        const val = r[metric];
                                                        const vals = results.map((rr) => rr[metric]).filter((v) => typeof v === 'number');
                                                        const best = Math.min(...vals);
                                                        const worst = Math.max(...vals);
                                                        const isBest = val === best && best !== worst;
                                                        const isWorst = val === worst && best !== worst;
                                                        return (_jsx("div", { className: `${isBest ? 'text-green-600 dark:text-green-400' : isWorst ? 'text-red-500 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`, children: typeof val === 'number' ? val.toFixed(2) : '-' }, i));
                                                    })] }, metric)))] }, eqId)))] })] }))] })] }));
}
