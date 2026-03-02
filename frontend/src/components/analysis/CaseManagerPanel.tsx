import { useState, useEffect } from 'react';
import { X, Save, Trash2, Upload, FolderOpen, GitCompare, Loader2 } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';

interface CaseData {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  property_package: string;
  simulation_basis: Record<string, unknown>;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  results: Record<string, unknown> | null;
  created_at: string;
}

interface CompareResult {
  cases: CaseData[];
  diffs: {
    property_packages: string[];
    node_counts: number[];
    edge_counts: number[];
    equipment_results: Record<string, Record<string, unknown>[]>;
    stream_results: Record<string, Record<string, unknown>[]>;
  };
}

interface CaseManagerPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function CaseManagerPanel({ open, onClose }: CaseManagerPanelProps) {
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);
  const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);
  const currentProjectId = useFlowsheetStore((s) => s.currentProjectId);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);
  const lastResults = useSimulationStore((s) => s.results);

  const [cases, setCases] = useState<CaseData[]>([]);
  const [caseName, setCaseName] = useState('');
  const [caseDesc, setCaseDesc] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchCases = async () => {
    if (!currentProjectId) return;
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/cases`);
      if (res.ok) {
        setCases(await res.json());
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    if (open && currentProjectId) {
      fetchCases();
    }
  }, [open, currentProjectId]);

  const saveCase = async () => {
    if (!currentProjectId || !caseName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const simNodes = nodes.map((n) => ({
        id: n.id,
        type: n.type,
        data: n.data,
        position: n.position,
      }));
      const simEdges = edges.map((e) => ({
        id: e.id,
        source: e.source,
        sourceHandle: e.sourceHandle ?? '',
        target: e.target,
        targetHandle: e.targetHandle ?? '',
        type: e.type,
      }));

      const res = await fetch(`/api/projects/${currentProjectId}/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: caseName.trim(),
          description: caseDesc.trim() || null,
          nodes: simNodes,
          edges: simEdges,
          simulation_basis: simulationBasis,
          property_package: propertyPackage,
          results: lastResults,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setCaseName('');
      setCaseDesc('');
      await fetchCases();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save case');
    } finally {
      setLoading(false);
    }
  };

  const loadCase = async (caseId: string) => {
    if (!currentProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/cases/${caseId}/load`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CaseData = await res.json();

      // Apply to flowsheet store — use setState for nodes/edges since there's no setter method
      useFlowsheetStore.setState({
        nodes: data.nodes as any,
        edges: data.edges as any,
      });
      if (data.simulation_basis) {
        useFlowsheetStore.getState().setSimulationBasis(data.simulation_basis as any);
      }
      if (data.property_package) {
        useSimulationStore.getState().setPropertyPackage(data.property_package);
      }
      if (data.results) {
        useSimulationStore.setState({ results: data.results as any });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load case');
    } finally {
      setLoading(false);
    }
  };

  const deleteCase = async (caseId: string) => {
    if (!currentProjectId) return;
    try {
      await fetch(`/api/projects/${currentProjectId}/cases/${caseId}`, {
        method: 'DELETE',
      });
      setSelectedIds(selectedIds.filter((id) => id !== caseId));
      await fetchCases();
    } catch {
      // ignore
    }
  };

  const toggleSelect = (caseId: string) => {
    setSelectedIds((prev) =>
      prev.includes(caseId) ? prev.filter((id) => id !== caseId) : [...prev, caseId]
    );
    setCompareResult(null);
  };

  const compareCases = async () => {
    if (!currentProjectId || selectedIds.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/cases/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_ids: selectedIds }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setCompareResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compare cases');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="absolute right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <FolderOpen size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Case Studies</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Save New Case */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider">
            Save Current State
          </label>
          <input
            type="text"
            value={caseName}
            onChange={(e) => setCaseName(e.target.value)}
            placeholder="Case name..."
            className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            value={caseDesc}
            onChange={(e) => setCaseDesc(e.target.value)}
            placeholder="Description (optional)..."
            className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={saveCase}
            disabled={!caseName.trim() || loading}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save Case
          </button>
        </div>

        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{error}</div>
        )}

        {/* Saved Cases */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider">
            Saved Cases ({cases.length})
          </label>
          {cases.length > 0 ? (
            <div className="space-y-2">
              {cases.map((c) => (
                <div
                  key={c.id}
                  className={`px-3 py-2 rounded border text-sm ${
                    selectedIds.includes(c.id)
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(c.id)}
                        onChange={() => toggleSelect(c.id)}
                        className="rounded border-gray-300 dark:border-gray-600"
                      />
                      <span className="font-medium text-gray-800 dark:text-gray-200 truncate">
                        {c.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => loadCase(c.id)}
                        title="Load case"
                        className="p-1 text-gray-400 hover:text-blue-400 transition-colors"
                      >
                        <Upload size={12} />
                      </button>
                      <button
                        onClick={() => deleteCase(c.id)}
                        title="Delete case"
                        className="p-1 text-gray-400 hover:text-red-400 transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 flex gap-3">
                    <span>{c.property_package}</span>
                    <span>{new Date(c.created_at).toLocaleDateString()}</span>
                  </div>
                  {c.description && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                      {c.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center">
              No saved cases. Save the current flowsheet state above.
            </div>
          )}
        </div>

        {/* Compare Button */}
        {selectedIds.length >= 2 && (
          <button
            onClick={compareCases}
            disabled={loading || selectedIds.length > 3}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-purple-600 text-white text-sm rounded hover:bg-purple-500 disabled:opacity-50"
          >
            <GitCompare size={14} />
            Compare {selectedIds.length} Cases
          </button>
        )}

        {/* Comparison Results */}
        {compareResult && (
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider">
              Comparison
            </label>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-3 text-xs space-y-2">
              {/* Header */}
              <div className="grid gap-1" style={{ gridTemplateColumns: `100px repeat(${compareResult.cases.length}, 1fr)` }}>
                <div className="font-semibold text-gray-500 dark:text-gray-400">Metric</div>
                {compareResult.cases.map((c) => (
                  <div key={c.id} className="font-semibold text-gray-700 dark:text-gray-300 truncate">
                    {c.name}
                  </div>
                ))}
              </div>
              {/* Property Package */}
              <div className="grid gap-1" style={{ gridTemplateColumns: `100px repeat(${compareResult.cases.length}, 1fr)` }}>
                <div className="text-gray-500">Prop. Pkg</div>
                {compareResult.diffs.property_packages.map((pp, i) => (
                  <div key={i} className="text-gray-700 dark:text-gray-300">{pp}</div>
                ))}
              </div>
              {/* Node Count */}
              <div className="grid gap-1" style={{ gridTemplateColumns: `100px repeat(${compareResult.cases.length}, 1fr)` }}>
                <div className="text-gray-500">Equipment</div>
                {compareResult.diffs.node_counts.map((n, i) => (
                  <div key={i} className="text-gray-700 dark:text-gray-300">{n}</div>
                ))}
              </div>
              {/* Equipment Results */}
              {Object.entries(compareResult.diffs.equipment_results).map(([eqId, results]) => (
                <div key={eqId}>
                  <div className="font-medium text-gray-600 dark:text-gray-400 mt-1 mb-0.5 truncate">{eqId}</div>
                  {results.length > 0 && Object.keys(results[0] || {}).filter((k) => typeof (results[0] as any)[k] === 'number').slice(0, 5).map((metric) => (
                    <div
                      key={metric}
                      className="grid gap-1"
                      style={{ gridTemplateColumns: `100px repeat(${results.length}, 1fr)` }}
                    >
                      <div className="text-gray-500 truncate">{metric}</div>
                      {results.map((r, i) => {
                        const val = (r as any)[metric];
                        const vals = results.map((rr) => (rr as any)[metric]).filter((v) => typeof v === 'number');
                        const best = Math.min(...vals);
                        const worst = Math.max(...vals);
                        const isBest = val === best && best !== worst;
                        const isWorst = val === worst && best !== worst;
                        return (
                          <div
                            key={i}
                            className={`${isBest ? 'text-green-600 dark:text-green-400' : isWorst ? 'text-red-500 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`}
                          >
                            {typeof val === 'number' ? val.toFixed(2) : '-'}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
