import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Play, Loader2, Bot, Beaker, XCircle, Undo2, Redo2, Settings2,
  Sun, Moon, Menu, History, Download, Upload, Archive, ChevronDown,
} from 'lucide-react';
import { toast } from 'sonner';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useThemeStore } from '../../stores/themeStore';
import { useVersionStore } from '../../stores/versionStore';
import { SimulationStatus } from '../../types';
import {
  exportFlowsheet,
  importFlowsheet,
  downloadBackup,
  exportSimulationResults,
} from '../../lib/api-client';
import { downloadBlob } from '../../lib/download-utils';
import { exportCanvasAsSvg, exportCanvasAsPng, exportCanvasAsPdf } from '../../lib/canvas-export';

export default function TopNav({ onToggleSidebar }: { onToggleSidebar?: () => void }) {
  const simulationStatus = useSimulationStore((s) => s.status);
  const runSimulation = useSimulationStore((s) => s.runSimulation);
  const cancelSimulation = useSimulationStore((s) => s.cancelSimulation);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);
  const setPropertyPackage = useSimulationStore((s) => s.setPropertyPackage);
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

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(projectName);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const exportRef = useRef<HTMLDivElement>(null);
  const importRef = useRef<HTMLInputElement>(null);

  // Close popovers on outside click
  useEffect(() => {
    if (!settingsOpen && !exportOpen) return;
    const handler = (e: MouseEvent) => {
      if (settingsOpen && settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
      if (exportOpen && exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [settingsOpen, exportOpen]);

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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') commitEdit();
    else if (e.key === 'Escape') setEditing(false);
  };

  const handleExportFlowsheet = useCallback(async (format: string) => {
    if (!projectId) return;
    setExportOpen(false);
    try {
      const res = await exportFlowsheet(projectId, format);
      const blob = await res.blob();
      const ext = format === 'json' ? 'prosim.json' : format === 'xml' ? 'prosim.xml' : 'dwxml';
      downloadBlob(blob, `${projectName}.${ext}`);
      toast.success(`Exported as ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(`Export failed: ${err instanceof Error ? err.message : 'unknown'}`);
    }
  }, [projectId, projectName]);

  const handleExportPfd = useCallback(async (format: string) => {
    setExportOpen(false);
    try {
      if (format === 'svg') await exportCanvasAsSvg();
      else if (format === 'png') await exportCanvasAsPng();
      else if (format === 'pdf') await exportCanvasAsPdf();
      toast.success(`PFD exported as ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(`PFD export failed: ${err instanceof Error ? err.message : 'unknown'}`);
    }
  }, []);

  const handleExportResults = useCallback(async (format: string) => {
    setExportOpen(false);
    if (!results) {
      toast.error('No simulation results to export');
      return;
    }
    try {
      const rawResults: Record<string, unknown> = {
        stream_results: results.streamResults,
        equipment_results: results.equipmentResults,
        convergence_info: results.convergenceInfo,
      };
      const res = await exportSimulationResults(rawResults, format);
      const blob = await res.blob();
      const ext = format === 'xlsx' ? 'xlsx' : 'csv';
      downloadBlob(blob, `simulation_results.${ext}`);
      toast.success(`Results exported as ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(`Export failed: ${err instanceof Error ? err.message : 'unknown'}`);
    }
  }, [results]);

  const handleImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    try {
      const result = await importFlowsheet(projectId, file);
      toast.success(`Imported ${result.nodes_imported} nodes, ${result.edges_imported} edges`);
      if (result.warnings?.length > 0) {
        toast.warning(result.warnings.join('; '));
      }
      await initProject();
    } catch (err) {
      toast.error(`Import failed: ${err instanceof Error ? err.message : 'unknown'}`);
    }
    // Reset input so same file can be re-imported
    e.target.value = '';
  }, [projectId, initProject]);

  const handleBackup = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await downloadBackup(projectId);
      const blob = await res.blob();
      downloadBlob(blob, `${projectName}.prosim-backup.json`);
      toast.success('Backup downloaded');
    } catch (err) {
      toast.error(`Backup failed: ${err instanceof Error ? err.message : 'unknown'}`);
    }
  }, [projectId, projectName]);

  const btnClass = 'p-1.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors';

  return (
    <nav className="h-12 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-4 z-50">
      <div className="flex items-center gap-3">
        <button onClick={onToggleSidebar} className="lg:hidden p-1 text-gray-300 hover:text-white">
          <Menu size={18} />
        </button>
        <Beaker size={20} className="text-blue-400" />
        <span className="text-sm font-bold text-gray-900 dark:text-gray-100 tracking-wide">ProSim Cloud</span>
        <span className="text-xs text-gray-500 hidden sm:inline">|</span>
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            className="text-xs text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 border border-gray-400 dark:border-gray-600 rounded px-1.5 py-0.5 outline-none focus:border-blue-500 hidden sm:inline"
            autoFocus
          />
        ) : (
          <span
            onClick={startEditing}
            className="text-xs text-gray-500 dark:text-gray-400 hidden sm:inline cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            title="Click to rename project"
          >
            {projectName}
          </span>
        )}
        <span
          className={`w-2 h-2 rounded-full hidden sm:inline-block ${
            saveStatus === 'saving' ? 'bg-yellow-400' : saveStatus === 'error' ? 'bg-red-400' : 'bg-green-400'
          }`}
          title={saveStatus === 'saving' ? 'Saving...' : saveStatus === 'error' ? 'Save failed' : 'Saved'}
        />
        <span className="text-xs text-gray-600 hidden sm:inline">|</span>
        <button
          onClick={undo} disabled={!canUndo()}
          className={`p-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${!canUndo() ? 'opacity-50 cursor-not-allowed' : ''}`}
          title="Undo (Ctrl+Z)"
        >
          <Undo2 size={14} />
        </button>
        <button
          onClick={redo} disabled={!canRedo()}
          className={`p-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${!canRedo() ? 'opacity-50 cursor-not-allowed' : ''}`}
          title="Redo (Ctrl+Shift+Z)"
        >
          <Redo2 size={14} />
        </button>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={propertyPackage}
          onChange={(e) => setPropertyPackage(e.target.value)}
          className="bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 text-sm rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500"
        >
          <option value="PengRobinson">Peng-Robinson</option>
          <option value="SRK">SRK</option>
          <option value="NRTL">NRTL</option>
          <option value="UNIQUAC">UNIQUAC</option>
        </select>

        {/* Convergence Settings */}
        <div className="relative" ref={settingsRef}>
          <button
            onClick={() => setSettingsOpen(!settingsOpen)}
            className={`p-1.5 rounded transition-colors ${
              settingsOpen ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
            title="Convergence Settings"
          >
            <Settings2 size={14} />
          </button>
          {settingsOpen && (
            <div className="absolute right-0 top-full mt-1 w-64 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-xl p-3 z-50">
              <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Convergence Settings</h4>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Max Iterations (1–500)</label>
              <input type="number" min={1} max={500} step={1} value={convergenceSettings.maxIter}
                onChange={(e) => setConvergenceSettings({ maxIter: Math.max(1, Math.min(500, Number(e.target.value) || 50)) })}
                className="w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 mb-2 focus:outline-none focus:border-blue-500" />
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Tolerance</label>
              <input type="number" min={1e-10} max={1} step={0.0001} value={convergenceSettings.tolerance}
                onChange={(e) => setConvergenceSettings({ tolerance: Math.max(1e-10, Math.min(1, Number(e.target.value) || 0.0001)) })}
                className="w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 mb-2 focus:outline-none focus:border-blue-500" />
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Damping Factor (0.01–1.0)</label>
              <input type="number" min={0.01} max={1} step={0.01} value={convergenceSettings.damping}
                onChange={(e) => setConvergenceSettings({ damping: Math.max(0.01, Math.min(1, Number(e.target.value) || 0.5)) })}
                className="w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-blue-500" />
            </div>
          )}
        </div>

        {/* History */}
        <button
          onClick={toggleVersionPanel}
          className={`${btnClass} ${versionPanelOpen ? '!bg-blue-600 !text-white' : ''}`}
          title="Version History"
        >
          <History size={14} />
        </button>

        {/* Export dropdown */}
        <div className="relative" ref={exportRef}>
          <button
            onClick={() => setExportOpen(!exportOpen)}
            className={`flex items-center gap-1 ${btnClass} ${exportOpen ? '!bg-blue-600 !text-white' : ''}`}
            title="Export"
          >
            <Download size={14} />
            <ChevronDown size={10} />
          </button>
          {exportOpen && (
            <div className="absolute right-0 top-full mt-1 w-52 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg shadow-xl z-50 py-1">
              <div className="px-3 py-1 text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Flowsheet
              </div>
              <button onClick={() => handleExportFlowsheet('json')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                JSON (ProSim)
              </button>
              <button onClick={() => handleExportFlowsheet('xml')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                XML (ProSim)
              </button>
              <button onClick={() => handleExportFlowsheet('dwsim_xml')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                DWSIM XML
              </button>
              <div className="border-t border-gray-200 dark:border-gray-700 my-1" />
              <div className="px-3 py-1 text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                PFD Image
              </div>
              <button onClick={() => handleExportPfd('svg')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                SVG
              </button>
              <button onClick={() => handleExportPfd('png')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                PNG
              </button>
              <button onClick={() => handleExportPfd('pdf')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                PDF
              </button>
              {results && (
                <>
                  <div className="border-t border-gray-200 dark:border-gray-700 my-1" />
                  <div className="px-3 py-1 text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Results
                  </div>
                  <button onClick={() => handleExportResults('csv')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                    CSV
                  </button>
                  <button onClick={() => handleExportResults('xlsx')} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
                    Excel (XLSX)
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Import */}
        <button onClick={() => importRef.current?.click()} className={btnClass} title="Import Flowsheet">
          <Upload size={14} />
        </button>
        <input
          ref={importRef}
          type="file"
          accept=".json,.xml,.dwxmz,.dwxml"
          className="hidden"
          onChange={handleImport}
        />

        {/* Backup */}
        <button onClick={handleBackup} className={btnClass} title="Download Backup">
          <Archive size={14} />
        </button>

        {/* Simulate */}
        <button
          onClick={runSimulation}
          disabled={isRunning}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            isRunning
              ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              : 'bg-green-600 text-white hover:bg-green-500'
          }`}
        >
          {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {isRunning ? 'Running...' : 'Simulate'}
        </button>

        {isRunning && (
          <button
            onClick={cancelSimulation}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors"
          >
            <XCircle size={14} />
            Cancel
          </button>
        )}

        {/* Theme */}
        <button
          onClick={toggleTheme}
          className={btnClass}
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>

        {/* AI */}
        <button
          onClick={toggleAgent}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            agentOpen
              ? 'bg-purple-600 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100'
          }`}
        >
          <Bot size={14} />
          AI
        </button>
      </div>
    </nav>
  );
}
