import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { X, Save, Trash2, RotateCcw, GitCompare } from 'lucide-react';
import { useVersionStore } from '../../stores/versionStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
export default function VersionPanel() {
    const panelOpen = useVersionStore((s) => s.panelOpen);
    const togglePanel = useVersionStore((s) => s.togglePanel);
    const versions = useVersionStore((s) => s.versions);
    const loading = useVersionStore((s) => s.loading);
    const loadVersions = useVersionStore((s) => s.loadVersions);
    const saveVersion = useVersionStore((s) => s.saveVersion);
    const removeVersion = useVersionStore((s) => s.removeVersion);
    const restore = useVersionStore((s) => s.restore);
    const computeDiff = useVersionStore((s) => s.computeDiff);
    const diffResult = useVersionStore((s) => s.diffResult);
    const projectId = useFlowsheetStore((s) => s.currentProjectId);
    const initProject = useFlowsheetStore((s) => s.initProject);
    const [label, setLabel] = useState('');
    const [diffV1, setDiffV1] = useState('');
    const [diffV2, setDiffV2] = useState('');
    useEffect(() => {
        if (panelOpen && projectId) {
            loadVersions(projectId);
        }
    }, [panelOpen, projectId]);
    if (!panelOpen)
        return null;
    const handleSave = async () => {
        if (!projectId)
            return;
        await saveVersion(projectId, label || undefined);
        setLabel('');
    };
    const handleRestore = async (v) => {
        if (!projectId)
            return;
        await restore(projectId, v.id);
        await initProject();
    };
    const handleDiff = async () => {
        if (!projectId || !diffV1 || !diffV2)
            return;
        await computeDiff(projectId, diffV1, diffV2);
    };
    const formatDate = (iso) => {
        const d = new Date(iso);
        return d.toLocaleString();
    };
    return (_jsxs("div", { className: "fixed right-0 top-12 bottom-0 w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl", children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: [_jsx("h3", { className: "text-sm font-semibold text-gray-900 dark:text-gray-100", children: "Version History" }), _jsx("button", { onClick: togglePanel, className: "p-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300", children: _jsx(X, { size: 16 }) })] }), _jsxs("div", { className: "px-4 py-3 border-b border-gray-200 dark:border-gray-800 space-y-2", children: [_jsx("input", { value: label, onChange: (e) => setLabel(e.target.value), placeholder: "Version label (optional)", className: "w-full text-xs bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-gray-800 dark:text-gray-200 focus:outline-none focus:border-blue-500" }), _jsxs("button", { onClick: handleSave, disabled: loading, className: "w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-500 disabled:opacity-50 transition-colors", children: [_jsx(Save, { size: 12 }), "Save Snapshot"] })] }), _jsxs("div", { className: "flex-1 overflow-y-auto", children: [versions.length === 0 && !loading && (_jsx("p", { className: "text-xs text-gray-500 dark:text-gray-400 px-4 py-3", children: "No versions saved yet." })), versions.map((v) => (_jsxs("div", { className: "px-4 py-2.5 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50", children: [_jsxs("div", { className: "flex items-center justify-between mb-1", children: [_jsxs("span", { className: "text-xs font-medium text-gray-900 dark:text-gray-100", children: ["v", v.version_number, v.label && _jsxs("span", { className: "ml-1.5 text-gray-500 dark:text-gray-400", children: ["\u2014 ", v.label] })] }), _jsxs("div", { className: "flex items-center gap-1", children: [_jsx("button", { onClick: () => handleRestore(v), className: "p-1 text-blue-500 hover:text-blue-400", title: "Restore this version", children: _jsx(RotateCcw, { size: 12 }) }), _jsx("button", { onClick: () => projectId && removeVersion(projectId, v.id), className: "p-1 text-red-500 hover:text-red-400", title: "Delete this version", children: _jsx(Trash2, { size: 12 }) })] })] }), _jsx("span", { className: "text-xs text-gray-500 dark:text-gray-400", children: formatDate(v.created_at) })] }, v.id)))] }), versions.length >= 2 && (_jsxs("div", { className: "px-4 py-3 border-t border-gray-200 dark:border-gray-800 space-y-2", children: [_jsx("h4", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300", children: "Compare Versions" }), _jsxs("div", { className: "flex gap-2", children: [_jsxs("select", { value: diffV1, onChange: (e) => setDiffV1(e.target.value), className: "flex-1 text-xs bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-1 text-gray-800 dark:text-gray-200", children: [_jsx("option", { value: "", children: "From" }), versions.map((v) => (_jsxs("option", { value: v.id, children: ["v", v.version_number] }, v.id)))] }), _jsxs("select", { value: diffV2, onChange: (e) => setDiffV2(e.target.value), className: "flex-1 text-xs bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-1 text-gray-800 dark:text-gray-200", children: [_jsx("option", { value: "", children: "To" }), versions.map((v) => (_jsxs("option", { value: v.id, children: ["v", v.version_number] }, v.id)))] }), _jsx("button", { onClick: handleDiff, disabled: !diffV1 || !diffV2, className: "px-2 py-1 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 text-xs rounded hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50", children: _jsx(GitCompare, { size: 12 }) })] }), diffResult && (_jsxs("div", { className: "text-xs text-gray-600 dark:text-gray-400 space-y-1 max-h-32 overflow-y-auto", children: [_jsxs("p", { className: "text-green-500", children: ["+", diffResult.added_nodes.length, " nodes added"] }), _jsxs("p", { className: "text-red-500", children: ["-", diffResult.removed_nodes.length, " nodes removed"] }), _jsxs("p", { className: "text-yellow-500", children: ["~", diffResult.modified_nodes.length, " nodes modified"] }), _jsxs("p", { className: "text-green-500", children: ["+", diffResult.added_edges.length, " edges added"] }), _jsxs("p", { className: "text-red-500", children: ["-", diffResult.removed_edges.length, " edges removed"] }), _jsxs("p", { className: "text-yellow-500", children: ["~", diffResult.modified_edges.length, " edges modified"] })] }))] }))] }));
}
