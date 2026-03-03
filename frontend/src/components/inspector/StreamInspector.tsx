import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { useUnitStore } from '../../stores/unitStore';
import { SimulationStatus, type StreamConditions } from '../../types';
import { X, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';

function fmt(v: number | undefined | null, decimals = 4): string {
  if (v == null || isNaN(v)) return '-';
  return v.toFixed(decimals);
}

function StreamPropertiesDisplay({ conditions }: { conditions: StreamConditions }) {
  const [compExpanded, setCompExpanded] = useState(true);
  const us = useUnitStore((s) => s.unitSystem);
  const cv = us.fromSI;
  const un = us.units;

  const hasComponents =
    conditions.component_molar_flows &&
    Object.keys(conditions.component_molar_flows).length > 0;

  return (
    <div className="space-y-3">
      {/* Bulk properties */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
          Conditions
        </h3>
        <div className="space-y-1.5">
          <PropertyRow label="Temperature" value={fmt(cv.temperature(conditions.temperature), 2)} unit={un.temperature} />
          <PropertyRow label="Pressure" value={fmt(cv.pressure(conditions.pressure), 2)} unit={un.pressure} />
          <PropertyRow label="Mass Flow" value={fmt(cv.massFlow(conditions.flowRate), 4)} unit={un.massFlow} />
          <PropertyRow label="Vapor Fraction" value={fmt(conditions.vapor_fraction, 4)} unit="" />
          {conditions.enthalpy != null && (
            <PropertyRow label="Enthalpy" value={fmt(cv.enthalpy(conditions.enthalpy), 2)} unit={un.enthalpy} />
          )}
          {conditions.molecular_weight != null && (
            <PropertyRow label="MW (mix)" value={fmt(conditions.molecular_weight, 2)} unit="g/mol" />
          )}
          {conditions.molar_flow != null && (
            <PropertyRow label="Molar Flow" value={fmt(cv.molarFlow(conditions.molar_flow), 4)} unit={un.molarFlow} />
          )}
        </div>
      </div>

      {/* Composition (mole fractions) */}
      {conditions.composition && Object.keys(conditions.composition).length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-800 pt-3">
          <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            Composition (Mole Fraction)
          </h3>
          <div className="space-y-1">
            {Object.entries(conditions.composition).map(([name, z]) => (
              <div key={name} className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400 truncate mr-2">{name}</span>
                <span className="text-gray-900 dark:text-gray-100 font-mono">{fmt(z, 6)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Component properties table */}
      {hasComponents && (
        <div className="border-t border-gray-200 dark:border-gray-800 pt-3">
          <button
            onClick={() => setCompExpanded(!compExpanded)}
            className="flex items-center gap-1 text-xs font-semibold text-blue-400 uppercase tracking-wider mb-2 hover:text-blue-300 transition-colors w-full"
          >
            {compExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            Component Properties
          </button>
          {compExpanded && (
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                    <th className="text-left py-1 pr-2">Component</th>
                    <th className="text-right py-1 px-1">Mass Frac</th>
                    <th className="text-right py-1 px-1">Molar Flow</th>
                    <th className="text-right py-1 pl-1">Mass Flow</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(conditions.component_molar_flows!).map((name) => (
                    <tr key={name} className="border-b border-gray-100 dark:border-gray-800/50">
                      <td className="py-1 pr-2 text-gray-600 dark:text-gray-400 truncate max-w-[80px]" title={name}>
                        {name}
                      </td>
                      <td className="py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100">
                        {fmt(conditions.mass_fractions?.[name], 4)}
                      </td>
                      <td className="py-1 px-1 text-right font-mono text-gray-900 dark:text-gray-100">
                        {fmt(conditions.component_molar_flows?.[name] != null ? cv.molarFlow(conditions.component_molar_flows![name]) : undefined, 4)}
                      </td>
                      <td className="py-1 pl-1 text-right font-mono text-gray-900 dark:text-gray-100">
                        {fmt(conditions.component_mass_flows?.[name] != null ? cv.massFlow(conditions.component_mass_flows![name]) : undefined, 4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="text-gray-500 dark:text-gray-400 font-semibold">
                    <td className="py-1 pr-2">Units</td>
                    <td className="py-1 px-1 text-right">-</td>
                    <td className="py-1 px-1 text-right">{un.molarFlow}</td>
                    <td className="py-1 pl-1 text-right">{un.massFlow}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PropertyRow({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-gray-900 dark:text-gray-100 font-mono">
        {value} <span className="text-gray-500 dark:text-gray-500 text-[10px]">{unit}</span>
      </span>
    </div>
  );
}

export default function StreamInspector() {
  const selectedEdgeId = useFlowsheetStore((s) => s.selectedEdgeId);
  const edges = useFlowsheetStore((s) => s.edges);
  const nodes = useFlowsheetStore((s) => s.nodes);
  const setSelectedEdge = useFlowsheetStore((s) => s.setSelectedEdge);
  const results = useSimulationStore((s) => s.results);
  const status = useSimulationStore((s) => s.status);

  if (!selectedEdgeId) return null;

  const edge = edges.find((e) => e.id === selectedEdgeId);
  if (!edge) return null;

  // Find source and target node names
  const sourceNode = nodes.find((n) => n.id === edge.source);
  const targetNode = nodes.find((n) => n.id === edge.target);
  const streamName = `${sourceNode?.data.name ?? 'Source'} → ${targetNode?.data.name ?? 'Target'}`;

  const streamResult =
    status === SimulationStatus.Completed && results?.streamResults
      ? results.streamResults[selectedEdgeId]
      : null;

  return (
    <div className="w-72 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Stream</h2>
        <button
          onClick={() => setSelectedEdge(null)}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Connection</label>
          <div className="text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5">
            {streamName}
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Type</label>
          <div className="text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5">
            {edge.type === 'energy-stream' ? 'Energy Stream' : 'Material Stream'}
          </div>
        </div>

        {streamResult ? (
          <div className="border-t border-gray-200 dark:border-gray-800 pt-3">
            <StreamPropertiesDisplay conditions={streamResult} />
          </div>
        ) : (
          <div className="text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center">
            {status === SimulationStatus.Completed
              ? 'No results for this stream'
              : 'Run simulation to see stream properties'}
          </div>
        )}
      </div>
    </div>
  );
}
