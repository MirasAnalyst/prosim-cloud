import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useRef, useEffect, useCallback } from 'react';
import { Play, Loader2, Bot, Beaker, XCircle, Undo2, Redo2, Settings2, Sun, Moon, Menu, History, Download, Upload, Archive, ChevronDown, FlaskConical, Wrench, BarChart3, } from 'lucide-react';
import { toast } from 'sonner';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useThemeStore } from '../../stores/themeStore';
import { useVersionStore } from '../../stores/versionStore';
import { useUnitStore } from '../../stores/unitStore';
import { UNIT_SYSTEMS } from '../../lib/unit-systems';
import { SimulationStatus } from '../../types';
import { exportFlowsheet, importFlowsheet, downloadBackup, exportSimulationResults, } from '../../lib/api-client';
import { downloadBlob } from '../../lib/download-utils';
import { exportCanvasAsSvg, exportCanvasAsPng, exportCanvasAsPdf } from '../../lib/canvas-export';
export default function TopNav({ onToggleSidebar, onToggleBasis, basisOpen, onToggleSensitivity, onToggleCases, onToggleDesignSpec, onToggleOptimization, onToggleDynamic, onTogglePinch, onToggleUtility, onToggleEmissions, onToggleReliefValve, onToggleHydraulics, onToggleControlValve, onTogglePhaseEnvelope, onToggleBinaryVLE, onToggleColumnProfile, onToggleInsights, }) {
    const simulationStatus = useSimulationStore((s) => s.status);
    const runSimulation = useSimulationStore((s) => s.runSimulation);
    const cancelSimulation = useSimulationStore((s) => s.cancelSimulation);
    const toggleAgent = useAgentStore((s) => s.togglePanel);
    const agentOpen = useAgentStore((s) => s.isOpen);
    const projectName = useFlowsheetStore((s) => s.projectName);
    const setProjectName = useFlowsheetStore((s) => s.setProjectName);
    const saveStatus = useFlowsheetStore((s) => s.saveStatus);
    const projectId = useFlowsheetStore((s) => s.currentProjectId);
    const initProject = useFlowsheetStore((s) => s.initProject);
    const undo = useFlowsheetStore((s) => s.undo);
    const redo = useFlowsheetStore((s) => s.redo);
    const canUndo = useFlowsheetStore((s) => s.canUndo);
    const canRedo = useFlowsheetStore((s) => s.canRedo);
    const convergenceSettings = useSimulationStore((s) => s.convergenceSettings);
    const setConvergenceSettings = useSimulationStore((s) => s.setConvergenceSettings);
    const results = useSimulationStore((s) => s.results);
    const theme = useThemeStore((s) => s.theme);
    const toggleTheme = useThemeStore((s) => s.toggleTheme);
    const toggleVersionPanel = useVersionStore((s) => s.togglePanel);
    const versionPanelOpen = useVersionStore((s) => s.panelOpen);
    const unitSystemName = useUnitStore((s) => s.unitSystemName);
    const setUnitSystem = useUnitStore((s) => s.setUnitSystem);
    const [editing, setEditing] = useState(false);
    const [editValue, setEditValue] = useState(projectName);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [exportOpen, setExportOpen] = useState(false);
    const [analysisOpen, setAnalysisOpen] = useState(false);
    const [toolsOpen, setToolsOpen] = useState(false);
    const inputRef = useRef(null);
    const settingsRef = useRef(null);
    const exportRef = useRef(null);
    const analysisRef = useRef(null);
    const toolsRef = useRef(null);
    const importRef = useRef(null);
    // Close popovers on outside click
    useEffect(() => {
        if (!settingsOpen && !exportOpen && !analysisOpen && !toolsOpen)
            return;
        const handler = (e) => {
            if (settingsOpen && settingsRef.current && !settingsRef.current.contains(e.target)) {
                setSettingsOpen(false);
            }
            if (exportOpen && exportRef.current && !exportRef.current.contains(e.target)) {
                setExportOpen(false);
            }
            if (analysisOpen && analysisRef.current && !analysisRef.current.contains(e.target)) {
                setAnalysisOpen(false);
            }
            if (toolsOpen && toolsRef.current && !toolsRef.current.contains(e.target)) {
                setToolsOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [settingsOpen, exportOpen, analysisOpen, toolsOpen]);
    const isRunning = simulationStatus === SimulationStatus.Running;
    const startEditing = () => {
        setEditValue(projectName);
        setEditing(true);
        setTimeout(() => inputRef.current?.select(), 0);
    };
    const commitEdit = () => {
        const trimmed = editValue.trim();
        if (trimmed && trimmed !== projectName) {
            setProjectName(trimmed);
        }
        setEditing(false);
    };
    const handleKeyDown = (e) => {
        if (e.key === 'Enter')
            commitEdit();
        else if (e.key === 'Escape')
            setEditing(false);
    };
    const handleExportFlowsheet = useCallback(async (format) => {
        if (!projectId)
            return;
        setExportOpen(false);
        try {
            const res = await exportFlowsheet(projectId, format);
            const blob = await res.blob();
            const ext = format === 'json' ? 'prosim.json' : format === 'xml' ? 'prosim.xml' : 'dwxml';
            downloadBlob(blob, `${projectName}.${ext}`);
            toast.success(`Exported as ${format.toUpperCase()}`);
        }
        catch (err) {
            toast.error(`Export failed: ${err instanceof Error ? err.message : 'unknown'}`);
        }
    }, [projectId, projectName]);
    const handleExportPfd = useCallback(async (format) => {
        setExportOpen(false);
        try {
            if (format === 'svg')
                await exportCanvasAsSvg();
            else if (format === 'png')
                await exportCanvasAsPng();
            else if (format === 'pdf')
                await exportCanvasAsPdf();
            toast.success(`PFD exported as ${format.toUpperCase()}`);
        }
        catch (err) {
            toast.error(`PFD export failed: ${err instanceof Error ? err.message : 'unknown'}`);
        }
    }, []);
    const handleExportResults = useCallback(async (format) => {
        setExportOpen(false);
        if (!results) {
            toast.error('No simulation results to export');
            return;
        }
        try {
            const rawResults = {
                stream_results: results.streamResults,
                equipment_results: results.equipmentResults,
                convergence_info: results.convergenceInfo,
            };
            const res = await exportSimulationResults(rawResults, format);
            const blob = await res.blob();
            const ext = format === 'xlsx' ? 'xlsx' : 'csv';
            downloadBlob(blob, `simulation_results.${ext}`);
            toast.success(`Results exported as ${format.toUpperCase()}`);
        }
        catch (err) {
            toast.error(`Export failed: ${err instanceof Error ? err.message : 'unknown'}`);
        }
    }, [results]);
    const handleImport = useCallback(async (e) => {
        const file = e.target.files?.[0];
        if (!file || !projectId)
            return;
        try {
            const result = await importFlowsheet(projectId, file);
            toast.success(`Imported ${result.nodes_imported} nodes, ${result.edges_imported} edges`);
            if (result.warnings?.length > 0) {
                toast.warning(result.warnings.join('; '));
            }
            await initProject();
        }
        catch (err) {
            toast.error(`Import failed: ${err instanceof Error ? err.message : 'unknown'}`);
        }
        // Reset input so same file can be re-imported
        e.target.value = '';
    }, [projectId, initProject]);
    const handleBackup = useCallback(async () => {
        if (!projectId)
            return;
        try {
            const res = await downloadBackup(projectId);
            const blob = await res.blob();
            downloadBlob(blob, `${projectName}.prosim-backup.json`);
            toast.success('Backup downloaded');
        }
        catch (err) {
            toast.error(`Backup failed: ${err instanceof Error ? err.message : 'unknown'}`);
        }
    }, [projectId, projectName]);
    const btnClass = 'p-1.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors';
    return (_jsxs("nav", { className: "h-12 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-4 z-50", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("button", { onClick: onToggleSidebar, className: "lg:hidden p-1 text-gray-300 hover:text-white", children: _jsx(Menu, { size: 18 }) }), _jsx(Beaker, { size: 20, className: "text-blue-400" }), _jsx("span", { className: "text-sm font-bold text-gray-900 dark:text-gray-100 tracking-wide", children: "ProSim Cloud" }), _jsx("span", { className: "text-xs text-gray-500 hidden sm:inline", children: "|" }), editing ? (_jsx("input", { ref: inputRef, value: editValue, onChange: (e) => setEditValue(e.target.value), onBlur: commitEdit, onKeyDown: handleKeyDown, className: "text-xs text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 border border-gray-400 dark:border-gray-600 rounded px-1.5 py-0.5 outline-none focus:border-blue-500 hidden sm:inline", autoFocus: true })) : (_jsx("span", { onClick: startEditing, className: "text-xs text-gray-500 dark:text-gray-400 hidden sm:inline cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 transition-colors", title: "Click to rename project", children: projectName })), _jsx("span", { className: `w-2 h-2 rounded-full hidden sm:inline-block ${saveStatus === 'saving' ? 'bg-yellow-400' : saveStatus === 'error' ? 'bg-red-400' : 'bg-green-400'}`, title: saveStatus === 'saving' ? 'Saving...' : saveStatus === 'error' ? 'Save failed' : 'Saved' }), _jsx("span", { className: "text-xs text-gray-600 hidden sm:inline", children: "|" }), _jsx("button", { onClick: undo, disabled: !canUndo(), className: `p-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${!canUndo() ? 'opacity-50 cursor-not-allowed' : ''}`, title: "Undo (Ctrl+Z)", children: _jsx(Undo2, { size: 14 }) }), _jsx("button", { onClick: redo, disabled: !canRedo(), className: `p-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${!canRedo() ? 'opacity-50 cursor-not-allowed' : ''}`, title: "Redo (Ctrl+Shift+Z)", children: _jsx(Redo2, { size: 14 }) })] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("button", { onClick: onToggleBasis, className: `${btnClass} ${basisOpen ? '!bg-blue-600 !text-white' : ''}`, title: "Simulation Basis", children: _jsx(FlaskConical, { size: 14 }) }), _jsx("select", { value: unitSystemName, onChange: (e) => setUnitSystem(e.target.value), className: "text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700 rounded px-1.5 py-1 focus:outline-none focus:border-blue-500 cursor-pointer", title: "Unit System", children: Object.values(UNIT_SYSTEMS).map((us) => (_jsx("option", { value: us.name, children: us.label }, us.name))) }), _jsxs("div", { className: "relative", ref: settingsRef, children: [_jsx("button", { onClick: () => setSettingsOpen(!settingsOpen), className: `p-1.5 rounded transition-colors ${settingsOpen ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'}`, title: "Convergence Settings", children: _jsx(Settings2, { size: 14 }) }), settingsOpen && (_jsxs("div", { className: "absolute right-0 top-full mt-1 w-64 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-xl p-3 z-50", children: [_jsx("h4", { className: "text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2", children: "Convergence Settings" }), _jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Max Iterations (1\u2013500)" }), _jsx("input", { type: "number", min: 1, max: 500, step: 1, value: convergenceSettings.maxIter, onChange: (e) => setConvergenceSettings({ maxIter: Math.max(1, Math.min(500, Number(e.target.value) || 50)) }), className: "w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 mb-2 focus:outline-none focus:border-blue-500" }), _jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Tolerance" }), _jsx("input", { type: "number", min: 1e-10, max: 1, step: 0.0001, value: convergenceSettings.tolerance, onChange: (e) => setConvergenceSettings({ tolerance: Math.max(1e-10, Math.min(1, Number(e.target.value) || 0.0001)) }), className: "w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 mb-2 focus:outline-none focus:border-blue-500" }), _jsx("label", { className: "block text-xs text-gray-500 dark:text-gray-400 mb-1", children: "Damping Factor (0.01\u20131.0)" }), _jsx("input", { type: "number", min: 0.01, max: 1, step: 0.01, value: convergenceSettings.damping, onChange: (e) => setConvergenceSettings({ damping: Math.max(0.01, Math.min(1, Number(e.target.value) || 0.5)) }), className: "w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-blue-500" })] }))] }), _jsx("button", { onClick: toggleVersionPanel, className: `${btnClass} ${versionPanelOpen ? '!bg-blue-600 !text-white' : ''}`, title: "Version History", children: _jsx(History, { size: 14 }) }), _jsxs("div", { className: "relative", ref: analysisRef, children: [_jsxs("button", { onClick: () => setAnalysisOpen(!analysisOpen), className: `flex items-center gap-1 ${btnClass} ${analysisOpen ? '!bg-blue-600 !text-white' : ''}`, title: "Analysis", children: [_jsx(BarChart3, { size: 14 }), _jsx(ChevronDown, { size: 10 })] }), analysisOpen && (_jsxs("div", { className: "absolute right-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-xl z-50 py-1", children: [_jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleSensitivity?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Sensitivity Analysis" }), _jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleCases?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Case Studies" }), _jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleDesignSpec?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Design Specifications" }), _jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleOptimization?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Optimization" }), _jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleDynamic?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Dynamic Simulation" }), _jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleColumnProfile?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Column Profiles" }), _jsx("button", { onClick: () => { setAnalysisOpen(false); onToggleInsights?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Optimization Insights" })] }))] }), _jsxs("div", { className: "relative", ref: toolsRef, children: [_jsxs("button", { onClick: () => setToolsOpen(!toolsOpen), className: `flex items-center gap-1 ${btnClass} ${toolsOpen ? '!bg-blue-600 !text-white' : ''}`, title: "Tools", children: [_jsx(Wrench, { size: 14 }), _jsx(ChevronDown, { size: 10 })] }), toolsOpen && (_jsxs("div", { className: "absolute right-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-xl z-50 py-1", children: [_jsx("button", { onClick: () => { setToolsOpen(false); onTogglePinch?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Pinch Analysis" }), _jsx("button", { onClick: () => { setToolsOpen(false); onToggleUtility?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Utility Summary" }), _jsx("button", { onClick: () => { setToolsOpen(false); onToggleEmissions?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Environmental Calc." }), _jsx("button", { onClick: () => { setToolsOpen(false); onToggleReliefValve?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Relief Valve Sizing" }), _jsx("button", { onClick: () => { setToolsOpen(false); onToggleHydraulics?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Pipe Hydraulics" }), _jsx("button", { onClick: () => { setToolsOpen(false); onToggleControlValve?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Control Valve Sizing" }), _jsx("div", { className: "border-t border-gray-200 dark:border-gray-700 my-1" }), _jsx("button", { onClick: () => { setToolsOpen(false); onTogglePhaseEnvelope?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Phase Envelope" }), _jsx("button", { onClick: () => { setToolsOpen(false); onToggleBinaryVLE?.(); }, className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Binary VLE Diagrams" })] }))] }), _jsxs("div", { className: "relative", ref: exportRef, children: [_jsxs("button", { onClick: () => setExportOpen(!exportOpen), className: `flex items-center gap-1 ${btnClass} ${exportOpen ? '!bg-blue-600 !text-white' : ''}`, title: "Export", children: [_jsx(Download, { size: 14 }), _jsx(ChevronDown, { size: 10 })] }), exportOpen && (_jsxs("div", { className: "absolute right-0 top-full mt-1 w-52 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-xl z-50 py-1", children: [_jsx("div", { className: "px-3 py-1 text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider", children: "Flowsheet" }), _jsx("button", { onClick: () => handleExportFlowsheet('json'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "JSON (ProSim)" }), _jsx("button", { onClick: () => handleExportFlowsheet('xml'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "XML (ProSim)" }), _jsx("button", { onClick: () => handleExportFlowsheet('dwsim_xml'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "DWSIM XML" }), _jsx("div", { className: "border-t border-gray-200 dark:border-gray-700 my-1" }), _jsx("div", { className: "px-3 py-1 text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider", children: "PFD Image" }), _jsx("button", { onClick: () => handleExportPfd('svg'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "SVG" }), _jsx("button", { onClick: () => handleExportPfd('png'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "PNG" }), _jsx("button", { onClick: () => handleExportPfd('pdf'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "PDF" }), results && (_jsxs(_Fragment, { children: [_jsx("div", { className: "border-t border-gray-200 dark:border-gray-700 my-1" }), _jsx("div", { className: "px-3 py-1 text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider", children: "Results" }), _jsx("button", { onClick: () => handleExportResults('csv'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "CSV" }), _jsx("button", { onClick: () => handleExportResults('xlsx'), className: "w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700", children: "Excel (XLSX)" })] }))] }))] }), _jsx("button", { onClick: () => importRef.current?.click(), className: btnClass, title: "Import Flowsheet", children: _jsx(Upload, { size: 14 }) }), _jsx("input", { ref: importRef, type: "file", accept: ".json,.xml,.dwxmz,.dwxml", className: "hidden", onChange: handleImport }), _jsx("button", { onClick: handleBackup, className: btnClass, title: "Download Backup", children: _jsx(Archive, { size: 14 }) }), _jsxs("button", { onClick: runSimulation, disabled: isRunning, className: `flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${isRunning
                            ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                            : 'bg-green-600 text-white hover:bg-green-500'}`, children: [isRunning ? _jsx(Loader2, { size: 14, className: "animate-spin" }) : _jsx(Play, { size: 14 }), isRunning ? 'Running...' : 'Simulate'] }), isRunning && (_jsxs("button", { onClick: cancelSimulation, className: "flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors", children: [_jsx(XCircle, { size: 14 }), "Cancel"] })), _jsx("button", { onClick: toggleTheme, className: btnClass, title: theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode', children: theme === 'dark' ? _jsx(Sun, { size: 14 }) : _jsx(Moon, { size: 14 }) }), _jsxs("button", { onClick: toggleAgent, className: `flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${agentOpen
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100'}`, children: [_jsx(Bot, { size: 14 }), "AI"] })] })] }));
}
