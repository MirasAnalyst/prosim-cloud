import { useState, useRef, useEffect } from 'react';
import { Play, Loader2, Bot, Beaker, XCircle, Undo2, Redo2, Settings2, Sun, Moon, Menu } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useThemeStore } from '../../stores/themeStore';
import { SimulationStatus } from '../../types';

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
  const undo = useFlowsheetStore((s) => s.undo);
  const redo = useFlowsheetStore((s) => s.redo);
  const canUndo = useFlowsheetStore((s) => s.canUndo);
  const canRedo = useFlowsheetStore((s) => s.canRedo);
  const convergenceSettings = useSimulationStore((s) => s.convergenceSettings);
  const setConvergenceSettings = useSimulationStore((s) => s.setConvergenceSettings);
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(projectName);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click
  useEffect(() => {
    if (!settingsOpen) return;
    const handler = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [settingsOpen]);

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
    if (e.key === 'Enter') {
      commitEdit();
    } else if (e.key === 'Escape') {
      setEditing(false);
    }
  };

  return (
    <nav className="h-12 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-4 z-50">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="lg:hidden p-1 text-gray-300 hover:text-white"
        >
          <Menu size={18} />
        </button>
        <Beaker size={20} className="text-blue-400" />
        <span className="text-sm font-bold text-gray-900 dark:text-gray-100 tracking-wide">
          ProSim Cloud
        </span>
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
            saveStatus === 'saving'
              ? 'bg-yellow-400'
              : saveStatus === 'error'
                ? 'bg-red-400'
                : 'bg-green-400'
          }`}
          title={saveStatus === 'saving' ? 'Saving...' : saveStatus === 'error' ? 'Save failed' : 'Saved'}
        />
        <span className="text-xs text-gray-600 hidden sm:inline">|</span>
        <button
          onClick={undo}
          disabled={!canUndo()}
          className={`p-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${
            !canUndo() ? 'opacity-50 cursor-not-allowed' : ''
          }`}
          title="Undo (Ctrl+Z)"
        >
          <Undo2 size={14} />
        </button>
        <button
          onClick={redo}
          disabled={!canRedo()}
          className={`p-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${
            !canRedo() ? 'opacity-50 cursor-not-allowed' : ''
          }`}
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
              <input
                type="number" min={1} max={500} step={1}
                value={convergenceSettings.maxIter}
                onChange={(e) => setConvergenceSettings({ maxIter: Math.max(1, Math.min(500, Number(e.target.value) || 50)) })}
                className="w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 mb-2 focus:outline-none focus:border-blue-500"
              />
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Tolerance</label>
              <input
                type="number" min={1e-10} max={1} step={0.0001}
                value={convergenceSettings.tolerance}
                onChange={(e) => setConvergenceSettings({ tolerance: Math.max(1e-10, Math.min(1, Number(e.target.value) || 0.0001)) })}
                className="w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 mb-2 focus:outline-none focus:border-blue-500"
              />
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Damping Factor (0.01–1.0)</label>
              <input
                type="number" min={0.01} max={1} step={0.01}
                value={convergenceSettings.damping}
                onChange={(e) => setConvergenceSettings({ damping: Math.max(0.01, Math.min(1, Number(e.target.value) || 0.5)) })}
                className="w-full bg-white dark:bg-gray-900 border border-gray-400 dark:border-gray-600 text-gray-800 dark:text-gray-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}
        </div>

        <button
          onClick={runSimulation}
          disabled={isRunning}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            isRunning
              ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              : 'bg-green-600 text-white hover:bg-green-500'
          }`}
        >
          {isRunning ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
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

        <button
          onClick={toggleTheme}
          className="p-1.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>

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
