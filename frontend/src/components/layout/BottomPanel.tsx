import { useState, useMemo, useEffect, useRef } from 'react';
import { ChevronUp, ChevronDown, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { SimulationStatus } from '../../types';

export default function BottomPanel() {
  const [expanded, setExpanded] = useState(false);
  const status = useSimulationStore((s) => s.status);
  const results = useSimulationStore((s) => s.results);
  const error = useSimulationStore((s) => s.error);
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);

  const prevStatus = useRef(status);
  useEffect(() => {
    if (
      prevStatus.current === SimulationStatus.Running &&
      (status === SimulationStatus.Completed || status === SimulationStatus.Error)
    ) {
      setExpanded(true);
    }
    prevStatus.current = status;
  }, [status]);

  const nodeNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const n of nodes) {
      map[n.id] = n.data?.name || n.data?.equipmentType || n.id;
    }
    return map;
  }, [nodes]);

  const getStreamName = (edgeId: string): string => {
    const edge = edges.find((e) => e.id === edgeId);
    if (!edge) return edgeId;
    const src = nodeNameMap[edge.source] || 'Unknown';
    const tgt = nodeNameMap[edge.target] || 'Unknown';
    return `${src} → ${tgt}`;
  };

  const formatComposition = (comp?: Record<string, number>): string => {
    if (!comp || Object.keys(comp).length === 0) return '—';
    return Object.entries(comp)
      .filter(([, v]) => v > 0.001)
      .map(([k, v]) => `${k}: ${v.toFixed(3)}`)
      .join(', ');
  };

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
              <div className="bg-gray-950 rounded-lg p-3 font-mono text-xs space-y-0.5">
                {results.logs.map((log, i) => (
                  <div
                    key={i}
                    className={
                      log.startsWith('ERROR:') || log.includes('ERROR:')
                        ? 'text-red-400'
                        : log.startsWith('WARNING:') || log.includes('WARNING:')
                          ? 'text-yellow-400'
                          : 'text-gray-400'
                    }
                  >
                    {log}
                  </div>
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
                    <th className="text-right py-1 pr-4">Temp (°C)</th>
                    <th className="text-right py-1 pr-4">Pressure (kPa)</th>
                    <th className="text-right py-1 pr-4">Flow (kg/s)</th>
                    <th className="text-right py-1 pr-4">VF</th>
                    <th className="text-left py-1">Composition</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(results.streamResults).map(([id, cond]) => {
                    const streamName = getStreamName(id);
                    const compStr = formatComposition(cond.composition);
                    return (
                      <tr key={id} className="text-gray-300 border-b border-gray-800/50">
                        <td className="py-1 pr-4 max-w-[200px] truncate" title={streamName}>
                          {streamName}
                        </td>
                        <td className="text-right py-1 pr-4">{cond.temperature.toFixed(1)}</td>
                        <td className="text-right py-1 pr-4">{cond.pressure.toFixed(1)}</td>
                        <td className="text-right py-1 pr-4">{cond.flowRate.toFixed(3)}</td>
                        <td className="text-right py-1 pr-4">{cond.vapor_fraction?.toFixed(3) ?? '—'}</td>
                        <td className="py-1 max-w-[300px] truncate text-gray-400" title={compStr}>
                          {compStr}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
