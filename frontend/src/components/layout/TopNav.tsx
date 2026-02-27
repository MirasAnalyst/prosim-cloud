import { Play, Loader2, Bot, Beaker } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useAgentStore } from '../../stores/agentStore';
import { SimulationStatus } from '../../types';

export default function TopNav() {
  const simulationStatus = useSimulationStore((s) => s.status);
  const runSimulation = useSimulationStore((s) => s.runSimulation);
  const toggleAgent = useAgentStore((s) => s.togglePanel);
  const agentOpen = useAgentStore((s) => s.isOpen);

  const isRunning = simulationStatus === SimulationStatus.Running;

  return (
    <nav className="h-12 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 z-50">
      <div className="flex items-center gap-3">
        <Beaker size={20} className="text-blue-400" />
        <span className="text-sm font-bold text-gray-100 tracking-wide">
          ProSim Cloud
        </span>
        <span className="text-xs text-gray-500 hidden sm:inline">|</span>
        <span className="text-xs text-gray-400 hidden sm:inline">
          Untitled Project
        </span>
      </div>

      <div className="flex items-center gap-2">
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
