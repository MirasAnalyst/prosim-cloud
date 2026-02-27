import { useState } from 'react';
import { ChevronUp, ChevronDown, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { SimulationStatus } from '../../types';

export default function BottomPanel() {
  const [expanded, setExpanded] = useState(false);
  const status = useSimulationStore((s) => s.status);
  const results = useSimulationStore((s) => s.results);
  const error = useSimulationStore((s) => s.error);

  if (status === SimulationStatus.Idle) return null;

  return (
    <div
      className={`bg-gray-900 border-t border-gray-800 transition-all ${
        expanded ? 'h-64' : 'h-10'
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full h-10 px-4 flex items-center justify-between text-sm hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {status === SimulationStatus.Error ? (
            <AlertTriangle size={14} className="text-red-400" />
          ) : status === SimulationStatus.Completed ? (
            <CheckCircle2 size={14} className="text-green-400" />
          ) : (
            <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
          <span className="text-gray-300 font-medium">
            {status === SimulationStatus.Running && 'Simulation Running...'}
            {status === SimulationStatus.Completed && 'Simulation Complete'}
            {status === SimulationStatus.Error && 'Simulation Error'}
          </span>
          {results?.convergenceInfo && (
            <span className="text-xs text-gray-500">
              ({results.convergenceInfo.iterations} iterations,{' '}
              {results.convergenceInfo.converged ? 'converged' : 'not converged'})
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronDown size={14} className="text-gray-400" />
        ) : (
          <ChevronUp size={14} className="text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="h-[calc(100%-2.5rem)] overflow-y-auto custom-scrollbar px-4 pb-4">
          {error && (
            <div className="mb-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-300">
              {error}
            </div>
          )}

          {results?.logs && results.logs.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Simulation Log
              </h3>
              <div className="bg-gray-950 rounded-lg p-3 font-mono text-xs text-gray-400 space-y-0.5">
                {results.logs.map((log, i) => (
                  <div key={i}>{log}</div>
                ))}
              </div>
            </div>
          )}

          {results?.streamResults && Object.keys(results.streamResults).length > 0 && (
            <div className="mt-3">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Stream Results
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-1 pr-4">Stream</th>
                    <th className="text-right py-1 pr-4">Temp (C)</th>
                    <th className="text-right py-1 pr-4">Pressure (kPa)</th>
                    <th className="text-right py-1">Flow (kg/s)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(results.streamResults).map(([id, cond]) => (
                    <tr key={id} className="text-gray-300 border-b border-gray-800/50">
                      <td className="py-1 pr-4">{id}</td>
                      <td className="text-right py-1 pr-4">{cond.temperature.toFixed(1)}</td>
                      <td className="text-right py-1 pr-4">{cond.pressure.toFixed(1)}</td>
                      <td className="text-right py-1">{cond.flowRate.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
