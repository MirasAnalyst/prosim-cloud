import { useState, useRef } from 'react';
import { Play, Loader2, Bot, Beaker, XCircle } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { SimulationStatus } from '../../types';

export default function TopNav() {
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

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(projectName);
  const inputRef = useRef<HTMLInputElement>(null);

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
    <nav className="h-12 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 z-50">
      <div className="flex items-center gap-3">
        <Beaker size={20} className="text-blue-400" />
        <span className="text-sm font-bold text-gray-100 tracking-wide">
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
            className="text-xs text-gray-200 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 outline-none focus:border-blue-500 hidden sm:inline"
            autoFocus
          />
        ) : (
          <span
            onClick={startEditing}
            className="text-xs text-gray-400 hidden sm:inline cursor-pointer hover:text-gray-200 transition-colors"
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
      </div>

      <div className="flex items-center gap-2">
        <select
          value={propertyPackage}
          onChange={(e) => setPropertyPackage(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500"
        >
          <option value="PengRobinson">Peng-Robinson</option>
          <option value="SRK">SRK</option>
          <option value="NRTL">NRTL</option>
        </select>

        <button
          onClick={runSimulation}
          disabled={isRunning}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            isRunning
              ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
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
          onClick={toggleAgent}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            agentOpen
              ? 'bg-purple-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-gray-100'
          }`}
        >
          <Bot size={14} />
          AI
        </button>
      </div>
    </nav>
  );
}
