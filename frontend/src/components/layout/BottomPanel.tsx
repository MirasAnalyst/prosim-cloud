import { Fragment, useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { ChevronUp, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, ArrowUp, ArrowDown, Download, ChevronDown as ChevronDownSmall } from 'lucide-react';
import { toast } from 'sonner';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useSimulationStore } from '../../stores/simulationStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useUnitStore } from '../../stores/unitStore';
import { SimulationStatus } from '../../types';
import { exportSimulationResults } from '../../lib/api-client';
import { downloadBlob } from '../../lib/download-utils';

type SortCol = 'stream' | 'temperature' | 'pressure' | 'flowRate' | 'vapor_fraction' | 'composition';
type SortDir = 'asc' | 'desc';

export default function BottomPanel() {
  const [expanded, setExpanded] = useState(false);
  const [sortCol, setSortCol] = useState<SortCol>('stream');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [expandedStreams, setExpandedStreams] = useState<Set<string>>(new Set());
  const status = useSimulationStore((s) => s.status);
  const results = useSimulationStore((s) => s.results);
  const progress = useSimulationStore((s) => s.progress);
  const error = useSimulationStore((s) => s.error);
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);
  const us = useUnitStore((s) => s.unitSystem);
  const u = us.units;
  const c = us.fromSI;

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

  const toggleSort = useCallback((col: SortCol) => {
    setSortDir((prev) => (sortCol === col ? (prev === 'asc' ? 'desc' : 'asc') : 'asc'));
    setSortCol(col);
  }, [sortCol]);

  const sortedStreamEntries = useMemo(() => {
    if (!results?.streamResults) return [];
    const entries = Object.entries(results.streamResults).map(([id, cond]) => ({
      id,
      streamName: getStreamName(id),
      ...cond,
    }));
    entries.sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case 'stream': cmp = a.streamName.localeCompare(b.streamName); break;
        case 'temperature': cmp = a.temperature - b.temperature; break;
        case 'pressure': cmp = a.pressure - b.pressure; break;
        case 'flowRate': cmp = a.flowRate - b.flowRate; break;
        case 'vapor_fraction': cmp = (a.vapor_fraction ?? 0) - (b.vapor_fraction ?? 0); break;
        case 'composition': cmp = formatComposition(a.composition).localeCompare(formatComposition(b.composition)); break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return entries;
  }, [results?.streamResults, sortCol, sortDir]);

  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const exportDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!exportDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (exportDropdownRef.current && !exportDropdownRef.current.contains(e.target as HTMLElement)) {
        setExportDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportDropdownOpen]);

  const toggleStreamExpand = useCallback((id: string) => {
    setExpandedStreams((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const exportCsv = useCallback(() => {
    if (sortedStreamEntries.length === 0) return;
    const header = `Stream,Temperature (${u.temperature}),Pressure (${u.pressure}),Flow (${u.massFlow}),VF,Enthalpy (${u.enthalpy}),Entropy (${u.entropy}),MW (g/mol),Molar Flow (${u.molarFlow}),Density (${u.density}),Cp (${u.heatCapacity}),Viscosity (${u.viscosity}),Therm Cond (${u.thermalConductivity}),Surf Tension (${u.surfaceTension}),Z Factor,Vol Flow (${u.volumetricFlow}),Composition,Component,Mole Frac,Mass Frac,Comp Molar Flow (mol/s),Comp Mass Flow (kg/s)`;
    const rows: string[] = [];
    for (const e of sortedStreamEntries) {
      rows.push(
        `"${e.streamName}",${c.temperature(e.temperature).toFixed(1)},${c.pressure(e.pressure).toFixed(1)},${c.massFlow(e.flowRate).toFixed(3)},${e.vapor_fraction?.toFixed(3) ?? ''},${e.enthalpy != null ? c.enthalpy(e.enthalpy).toFixed(2) : ''},${e.entropy != null ? c.entropy(e.entropy).toFixed(4) : ''},${e.molecular_weight?.toFixed(2) ?? ''},${e.molar_flow != null ? c.molarFlow(e.molar_flow).toFixed(4) : ''},${e.density != null ? c.density(e.density).toFixed(2) : ''},${e.Cp_mass != null ? c.heatCapacity(e.Cp_mass).toFixed(1) : ''},${e.viscosity != null ? c.viscosity(e.viscosity).toFixed(6) : ''},${e.thermal_conductivity != null ? c.thermalConductivity(e.thermal_conductivity).toFixed(6) : ''},${e.surface_tension != null ? c.surfaceTension(e.surface_tension).toFixed(4) : ''},${e.Z_factor ?? ''},${e.volumetric_flow != null ? c.volumetricFlow(e.volumetric_flow).toFixed(6) : ''},"${formatComposition(e.composition)}",,,,, `
      );
      if (e.component_molar_flows && Object.keys(e.component_molar_flows).length > 0) {
        const comps = Object.keys(e.component_molar_flows);
        for (const c of comps) {
          const zz = e.composition?.[c] ?? 0;
          const ww = e.mass_fractions?.[c] ?? 0;
          const mf = e.component_molar_flows?.[c] ?? 0;
          const msf = e.component_mass_flows?.[c] ?? 0;
          rows.push(`,,,,,,,,,${c},${zz.toFixed(6)},${ww.toFixed(6)},${mf.toFixed(6)},${msf.toFixed(6)}`);
        }
      }
    }
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'stream_results.csv';
    a.click();
    URL.revokeObjectURL(url);
    setExportDropdownOpen(false);
  }, [sortedStreamEntries]);

  const exportExcel = useCallback(async () => {
    if (!results) return;
    setExportDropdownOpen(false);
    try {
      const rawResults: Record<string, unknown> = {
        stream_results: results.streamResults,
        equipment_results: results.equipmentResults,
        convergence_info: results.convergenceInfo,
      };
      const res = await exportSimulationResults(rawResults, 'xlsx');
      const blob = await res.blob();
      downloadBlob(blob, 'simulation_results.xlsx');
      toast.success('Results exported as Excel');
    } catch (err) {
      toast.error(`Export failed: ${err instanceof Error ? err.message : 'unknown'}`);
    }
  }, [results]);

  if (status === SimulationStatus.Idle) return null;

  return (
    <div
      className={`bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 transition-all ${
        expanded ? (expandedStreams.size > 0 ? 'h-[50vh]' : 'h-64') : 'h-10'
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full h-10 px-4 flex items-center justify-between text-sm hover:bg-gray-100/50 dark:hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {status === SimulationStatus.Error ? (
            <AlertTriangle size={14} className="text-red-400" />
          ) : status === SimulationStatus.Completed ? (
            <CheckCircle2 size={14} className="text-green-400" />
          ) : (
            <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
          <span className="text-gray-700 dark:text-gray-300 font-medium">
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
          {status === SimulationStatus.Running && (
            <div className="px-4 py-2 space-y-2">
              {progress && (
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${(progress.index / progress.total) * 100}%` }} />
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {progress.equipment} ({progress.index}/{progress.total})
                  </span>
                </div>
              )}
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex gap-4">
                  <div className="animate-pulse bg-gray-700 dark:bg-gray-700 rounded h-4 w-24" />
                  <div className="animate-pulse bg-gray-700 dark:bg-gray-700 rounded h-4 w-16" />
                  <div className="animate-pulse bg-gray-700 dark:bg-gray-700 rounded h-4 w-16" />
                  <div className="animate-pulse bg-gray-700 dark:bg-gray-700 rounded h-4 w-16" />
                </div>
              ))}
            </div>
          )}
          {error && (
            <div className="mb-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-300">
              {error}
            </div>
          )}

          {results?.logs && results.logs.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                Simulation Log
              </h3>
              <div className="bg-gray-50 dark:bg-gray-950 rounded-lg p-3 font-mono text-xs space-y-0.5">
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

          {/* Convergence History Chart (T2-5) */}
          {results?.convergenceInfo?.history && results.convergenceInfo.history.length > 1 && (
            <div className="mt-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                Convergence History ({results.convergenceInfo.history.length} iterations)
              </h3>
              <ResponsiveContainer width="100%" height={120}>
                <LineChart data={results.convergenceInfo.history} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="iteration" tick={{ fontSize: 9 }} label={{ value: 'Iteration', position: 'bottom', offset: -2, style: { fontSize: 9 } }} />
                  <YAxis scale="log" domain={['auto', 'auto']} tick={{ fontSize: 9 }} label={{ value: 'Error', angle: -90, position: 'left', offset: -5, style: { fontSize: 9 } }} />
                  <Tooltip contentStyle={{ fontSize: 10, backgroundColor: '#1f2937', border: '1px solid #374151' }} />
                  <Line type="monotone" dataKey="max_error" stroke="#ef4444" dot={false} strokeWidth={2} name="Max Error" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {sortedStreamEntries.length > 0 && (
            <div className="mt-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Stream Results
                </h3>
                <div className="relative" ref={exportDropdownRef}>
                  <button
                    onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
                    className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                  >
                    <Download size={12} />
                    Export
                    <ChevronDownSmall size={10} />
                  </button>
                  {exportDropdownOpen && (
                    <div className="absolute right-0 bottom-full mb-1 w-32 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded shadow-lg z-50 py-1">
                      <button onClick={exportCsv} className="w-full text-left px-3 py-1 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">CSV</button>
                      <button onClick={exportExcel} className="w-full text-left px-3 py-1 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">Excel (XLSX)</button>
                    </div>
                  )}
                </div>
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-200 dark:border-gray-800">
                    {([
                      ['stream', 'text-left', 'Stream'],
                      ['temperature', 'text-right', `Temp (${u.temperature})`],
                      ['pressure', 'text-right', `Pressure (${u.pressure})`],
                      ['flowRate', 'text-right', `Flow (${u.massFlow})`],
                      ['vapor_fraction', 'text-right', 'VF'],
                      ['composition', 'text-left', 'Composition'],
                    ] as [SortCol, string, string][]).map(([col, align, label]) => (
                      <th
                        key={col}
                        className={`${align} py-1 pr-4 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-300 transition-colors`}
                        onClick={() => toggleSort(col)}
                      >
                        <span className="inline-flex items-center gap-0.5">
                          {label}
                          {sortCol === col && (
                            sortDir === 'asc'
                              ? <ArrowUp size={10} />
                              : <ArrowDown size={10} />
                          )}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedStreamEntries.map((entry) => {
                    const compStr = formatComposition(entry.composition);
                    const hasComponents = entry.component_molar_flows && Object.keys(entry.component_molar_flows).length > 0;
                    const isExpanded = expandedStreams.has(entry.id);
                    return (
                      <Fragment key={entry.id}>
                        <tr
                          className={`text-gray-700 dark:text-gray-300 border-b border-gray-200/50 dark:border-gray-800/50 ${hasComponents ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50' : ''}`}
                          onClick={() => hasComponents && toggleStreamExpand(entry.id)}
                        >
                          <td className="py-1 pr-4 max-w-[200px] truncate" title={entry.streamName}>
                            <span className="inline-flex items-center gap-1">
                              {hasComponents && (
                                isExpanded
                                  ? <ChevronDown size={10} className="text-gray-400 flex-shrink-0" />
                                  : <ChevronRight size={10} className="text-gray-400 flex-shrink-0" />
                              )}
                              {entry.streamName}
                            </span>
                          </td>
                          <td className="text-right py-1 pr-4">{c.temperature(entry.temperature).toFixed(1)}</td>
                          <td className="text-right py-1 pr-4">{c.pressure(entry.pressure).toFixed(1)}</td>
                          <td className="text-right py-1 pr-4">{c.massFlow(entry.flowRate).toFixed(3)}</td>
                          <td className="text-right py-1 pr-4">{entry.vapor_fraction?.toFixed(3) ?? '\u2014'}</td>
                          <td className="py-1 max-w-[300px] truncate text-gray-500 dark:text-gray-400" title={compStr}>
                            {compStr}
                          </td>
                        </tr>
                        {isExpanded && hasComponents && (
                          <tr key={`${entry.id}-details`} className="bg-gray-50/50 dark:bg-gray-800/30">
                            <td colSpan={6} className="px-4 py-2">
                              {/* Bulk stream properties */}
                              <div className="text-[11px] text-gray-500 dark:text-gray-400 mb-1.5 flex flex-wrap gap-x-3">
                                <span>MW: {entry.molecular_weight?.toFixed(2) ?? '—'} g/mol</span>
                                <span>Molar Flow: {entry.molar_flow != null ? c.molarFlow(entry.molar_flow).toFixed(4) : '—'} {u.molarFlow}</span>
                                <span>H: {entry.enthalpy != null ? c.enthalpy(entry.enthalpy).toFixed(2) : '—'} {u.enthalpy}</span>
                                <span>S: {entry.entropy != null ? c.entropy(entry.entropy).toFixed(4) : '—'} {u.entropy}</span>
                                {entry.density != null && <span>ρ: {c.density(entry.density).toFixed(2)} {u.density}</span>}
                                {entry.Cp_mass != null && <span>Cp: {c.heatCapacity(entry.Cp_mass).toFixed(1)} {u.heatCapacity}</span>}
                                {entry.Cv_mass != null && <span>Cv: {c.heatCapacity(entry.Cv_mass).toFixed(1)} {u.heatCapacity}</span>}
                                {entry.Z_factor != null && <span>Z: {entry.Z_factor.toFixed(4)}</span>}
                                {entry.viscosity != null && <span>μ: {c.viscosity(entry.viscosity).toFixed(4)} {u.viscosity}</span>}
                                {entry.thermal_conductivity != null && <span>k: {c.thermalConductivity(entry.thermal_conductivity).toFixed(4)} {u.thermalConductivity}</span>}
                                {entry.surface_tension != null && <span>σ: {c.surfaceTension(entry.surface_tension).toFixed(2)} {u.surfaceTension}</span>}
                                {entry.volumetric_flow != null && <span>Q: {(() => { const qv = c.volumetricFlow(entry.volumetric_flow!); return qv < 0.01 ? qv.toExponential(3) : qv.toFixed(4); })()} {u.volumetricFlow}</span>}
                              </div>
                              {/* Phase-specific properties */}
                              {entry.phase_properties && (
                                <div className="flex gap-6 text-[11px] text-gray-400 dark:text-gray-500 mb-2">
                                  {entry.vapor_fraction > 0.001 && entry.phase_properties.vapor && (
                                    <div>
                                      <span className="font-medium text-red-400">Vapor:</span>
                                      {entry.phase_properties.vapor.density != null && <span className="ml-2">ρ={c.density(entry.phase_properties.vapor.density).toFixed(3)} {u.density}</span>}
                                      {entry.phase_properties.vapor.viscosity != null && <span className="ml-2">μ={c.viscosity(entry.phase_properties.vapor.viscosity).toFixed(4)} {u.viscosity}</span>}
                                      {entry.phase_properties.vapor.Cp != null && <span className="ml-2">Cp={c.heatCapacity(entry.phase_properties.vapor.Cp).toFixed(1)} {u.heatCapacity}</span>}
                                      {entry.phase_properties.vapor.Z != null && <span className="ml-2">Z={entry.phase_properties.vapor.Z.toFixed(4)}</span>}
                                    </div>
                                  )}
                                  {entry.vapor_fraction < 0.999 && entry.phase_properties.liquid && (
                                    <div>
                                      <span className="font-medium text-blue-400">Liquid:</span>
                                      {entry.phase_properties.liquid.density != null && <span className="ml-2">ρ={c.density(entry.phase_properties.liquid.density).toFixed(1)} {u.density}</span>}
                                      {entry.phase_properties.liquid.viscosity != null && <span className="ml-2">μ={c.viscosity(entry.phase_properties.liquid.viscosity).toFixed(4)} {u.viscosity}</span>}
                                      {entry.phase_properties.liquid.Cp != null && <span className="ml-2">Cp={c.heatCapacity(entry.phase_properties.liquid.Cp).toFixed(1)} {u.heatCapacity}</span>}
                                      {entry.phase_properties.liquid.thermal_conductivity != null && <span className="ml-2">k={c.thermalConductivity(entry.phase_properties.liquid.thermal_conductivity).toFixed(4)} {u.thermalConductivity}</span>}
                                      {entry.surface_tension != null && <span className="ml-2">σ={c.surfaceTension(entry.surface_tension).toFixed(2)} {u.surfaceTension}</span>}
                                    </div>
                                  )}
                                </div>
                              )}
                              {/* Component table */}
                              <table className="w-full text-[11px]">
                                <thead>
                                  <tr className="text-gray-400 dark:text-gray-500">
                                    <th className="text-left py-0.5 pr-4 font-medium">Component</th>
                                    <th className="text-right py-0.5 pr-4 font-medium">Mole Frac</th>
                                    <th className="text-right py-0.5 pr-4 font-medium">Mass Frac</th>
                                    <th className="text-right py-0.5 pr-4 font-medium">Molar Flow ({u.molarFlow})</th>
                                    <th className="text-right py-0.5 font-medium">Mass Flow ({u.massFlow})</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.keys(entry.component_molar_flows!).map((comp) => (
                                    <tr key={comp} className="text-gray-600 dark:text-gray-400">
                                      <td className="py-0.5 pr-4">{comp}</td>
                                      <td className="text-right py-0.5 pr-4">{(entry.composition?.[comp] ?? 0).toFixed(4)}</td>
                                      <td className="text-right py-0.5 pr-4">{(entry.mass_fractions?.[comp] ?? 0).toFixed(4)}</td>
                                      <td className="text-right py-0.5 pr-4">{c.molarFlow(entry.component_molar_flows![comp]).toFixed(4)}</td>
                                      <td className="text-right py-0.5">{c.massFlow(entry.component_mass_flows?.[comp] ?? 0).toFixed(4)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </td>
                          </tr>
                        )}
                      </Fragment>
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
