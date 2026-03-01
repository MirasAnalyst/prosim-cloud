import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { ChevronUp, ChevronDown, AlertTriangle, CheckCircle2, ArrowUp, ArrowDown, Download, ChevronDown as ChevronDownSmall } from 'lucide-react';
import { toast } from 'sonner';
import { useSimulationStore } from '../../stores/simulationStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { SimulationStatus } from '../../types';
import { exportSimulationResults } from '../../lib/api-client';
import { downloadBlob } from '../../lib/download-utils';

type SortCol = 'stream' | 'temperature' | 'pressure' | 'flowRate' | 'vapor_fraction' | 'composition';
type SortDir = 'asc' | 'desc';

export default function BottomPanel() {
  const [expanded, setExpanded] = useState(false);
  const [sortCol, setSortCol] = useState<SortCol>('stream');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const status = useSimulationStore((s) => s.status);
  const results = useSimulationStore((s) => s.results);
  const progress = useSimulationStore((s) => s.progress);
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

  const exportCsv = useCallback(() => {
    if (sortedStreamEntries.length === 0) return;
    const header = 'Stream,Temperature (C),Pressure (kPa),Flow (kg/s),VF,Composition';
    const rows = sortedStreamEntries.map((e) =>
      `"${e.streamName}",${e.temperature.toFixed(1)},${e.pressure.toFixed(1)},${e.flowRate.toFixed(3)},${e.vapor_fraction?.toFixed(3) ?? ''},"${formatComposition(e.composition)}"`
    );
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
        expanded ? 'h-64' : 'h-10'
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
                      ['temperature', 'text-right', 'Temp (\u00B0C)'],
                      ['pressure', 'text-right', 'Pressure (kPa)'],
                      ['flowRate', 'text-right', 'Flow (kg/s)'],
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
                    return (
                      <tr key={entry.id} className="text-gray-700 dark:text-gray-300 border-b border-gray-200/50 dark:border-gray-800/50">
                        <td className="py-1 pr-4 max-w-[200px] truncate" title={entry.streamName}>
                          {entry.streamName}
                        </td>
                        <td className="text-right py-1 pr-4">{entry.temperature.toFixed(1)}</td>
                        <td className="text-right py-1 pr-4">{entry.pressure.toFixed(1)}</td>
                        <td className="text-right py-1 pr-4">{entry.flowRate.toFixed(3)}</td>
                        <td className="text-right py-1 pr-4">{entry.vapor_fraction?.toFixed(3) ?? '\u2014'}</td>
                        <td className="py-1 max-w-[300px] truncate text-gray-500 dark:text-gray-400" title={compStr}>
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
