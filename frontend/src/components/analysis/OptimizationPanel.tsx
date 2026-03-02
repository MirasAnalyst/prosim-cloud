import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { EquipmentType } from '../../types';

const RESULT_KEYS = [
  { value: 'duty', label: 'Duty (kW)' },
  { value: 'work', label: 'Work (kW)' },
  { value: 'outletTemperature', label: 'Outlet Temp (°C)' },
  { value: 'vaporFraction', label: 'Vapor Fraction' },
  { value: 'massFlow', label: 'Mass Flow (kg/s)' },
  { value: 'outletPressure', label: 'Outlet Pressure (kPa)' },
];

interface DecisionVar {
  nodeId: string;
  paramKey: string;
  min: number;
  max: number;
}

interface Constraint {
  nodeId: string;
  resultKey: string;
  operator: string;
  value: number;
}

interface OptimizationPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function OptimizationPanel({ open, onClose }: OptimizationPanelProps) {
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);
  const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);

  const [objNodeId, setObjNodeId] = useState('');
  const [objKey, setObjKey] = useState('');
  const [objSense, setObjSense] = useState('minimize');
  const [solver, setSolver] = useState('SLSQP');
  const [maxIter, setMaxIter] = useState(100);
  const [dvars, setDvars] = useState<DecisionVar[]>([]);
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const equipmentNodes = nodes.filter((n: any) => {
    const t = n.data?.equipmentType || n.type;
    return t && t !== 'equipment';
  });

  const getParamKeys = (nodeId: string) => {
    const node = nodes.find((n: any) => n.id === nodeId);
    if (!node) return [];
    const eqType = (node as any).data?.equipmentType;
    if (!eqType || !(eqType in equipmentLibrary)) return [];
    return Object.keys(equipmentLibrary[eqType as EquipmentType].parameters);
  };

  const addDvar = () => setDvars([...dvars, { nodeId: '', paramKey: '', min: 0, max: 100 }]);
  const addConstraint = () => setConstraints([...constraints, { nodeId: '', resultKey: '', operator: '<=', value: 0 }]);

  const run = async () => {
    if (!objNodeId || !objKey || dvars.length === 0) return;
    setRunning(true);
    setError('');
    try {
      const res = await fetch('/api/simulation/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_nodes: nodes,
          base_edges: edges.map((e: any) => ({ ...e, type: e.type ?? 'stream' })),
          property_package: propertyPackage,
          simulation_basis: simulationBasis,
          objective: { node_id: objNodeId, result_key: objKey, sense: objSense },
          decision_variables: dvars.map((d) => ({
            node_id: d.nodeId, parameter_key: d.paramKey,
            min_value: d.min, max_value: d.max,
          })),
          constraints: constraints.map((c) => ({
            node_id: c.nodeId, result_key: c.resultKey,
            operator: c.operator, value: c.value,
          })),
          solver,
          max_iterations: maxIter,
        }),
      });
      const data = await res.json();
      if (data.error) setError(data.error);
      else setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setRunning(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed right-0 top-12 bottom-0 w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Optimization</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Objective */}
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Objective</label>
          <div className="flex gap-1">
            <select value={objNodeId} onChange={(e) => setObjNodeId(e.target.value)}
              className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="">Equipment</option>
              {equipmentNodes.map((n: any) => <option key={n.id} value={n.id}>{n.data?.name || n.id.slice(0, 8)}</option>)}
            </select>
            <select value={objKey} onChange={(e) => setObjKey(e.target.value)}
              className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="">Result</option>
              {RESULT_KEYS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
            <select value={objSense} onChange={(e) => setObjSense(e.target.value)}
              className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="minimize">Min</option>
              <option value="maximize">Max</option>
            </select>
          </div>
        </div>

        {/* Decision Variables */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Decision Variables</label>
            <button onClick={addDvar} className="text-xs text-blue-500 hover:text-blue-400">+ Add</button>
          </div>
          {dvars.map((dv, i) => (
            <div key={i} className="flex gap-1 mb-1">
              <select value={dv.nodeId} onChange={(e) => { const d = [...dvars]; d[i].nodeId = e.target.value; setDvars(d); }}
                className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5">
                <option value="">Equip</option>
                {equipmentNodes.map((n: any) => <option key={n.id} value={n.id}>{n.data?.name || n.id.slice(0, 8)}</option>)}
              </select>
              <select value={dv.paramKey} onChange={(e) => { const d = [...dvars]; d[i].paramKey = e.target.value; setDvars(d); }}
                className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5">
                <option value="">Param</option>
                {dv.nodeId && getParamKeys(dv.nodeId).map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
              <input type="number" placeholder="Min" value={dv.min} onChange={(e) => { const d = [...dvars]; d[i].min = Number(e.target.value); setDvars(d); }}
                className="w-14 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <input type="number" placeholder="Max" value={dv.max} onChange={(e) => { const d = [...dvars]; d[i].max = Number(e.target.value); setDvars(d); }}
                className="w-14 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <button onClick={() => setDvars(dvars.filter((_, j) => j !== i))} className="text-red-400 text-xs">×</button>
            </div>
          ))}
        </div>

        {/* Constraints */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400">Constraints</label>
            <button onClick={addConstraint} className="text-xs text-blue-500 hover:text-blue-400">+ Add</button>
          </div>
          {constraints.map((c, i) => (
            <div key={i} className="flex gap-1 mb-1">
              <select value={c.nodeId} onChange={(e) => { const cs = [...constraints]; cs[i].nodeId = e.target.value; setConstraints(cs); }}
                className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5">
                <option value="">Equip</option>
                {equipmentNodes.map((n: any) => <option key={n.id} value={n.id}>{n.data?.name || n.id.slice(0, 8)}</option>)}
              </select>
              <select value={c.resultKey} onChange={(e) => { const cs = [...constraints]; cs[i].resultKey = e.target.value; setConstraints(cs); }}
                className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5">
                <option value="">Result</option>
                {RESULT_KEYS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
              <select value={c.operator} onChange={(e) => { const cs = [...constraints]; cs[i].operator = e.target.value; setConstraints(cs); }}
                className="w-12 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5">
                <option value="<=">≤</option>
                <option value=">=">≥</option>
                <option value="==">=</option>
              </select>
              <input type="number" value={c.value} onChange={(e) => { const cs = [...constraints]; cs[i].value = Number(e.target.value); setConstraints(cs); }}
                className="w-16 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <button onClick={() => setConstraints(constraints.filter((_, j) => j !== i))} className="text-red-400 text-xs">×</button>
            </div>
          ))}
        </div>

        {/* Solver settings */}
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-[10px] text-gray-500">Solver</label>
            <select value={solver} onChange={(e) => setSolver(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="SLSQP">SLSQP</option>
              <option value="differential_evolution">Differential Evolution</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-[10px] text-gray-500">Max Iterations</label>
            <input type="number" value={maxIter} onChange={(e) => setMaxIter(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>

        <button onClick={run} disabled={running}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Optimizing...' : 'Optimize'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="space-y-2">
            <div className="bg-gray-50 dark:bg-gray-800 rounded p-3">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Status: {results.status} | Iterations: {results.iterations}
              </div>
              {results.objective_value != null && (
                <div className="text-xs text-gray-600 dark:text-gray-400">Objective: {results.objective_value}</div>
              )}
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mt-2">Optimal Values:</div>
              {Object.entries(results.optimal_values || {}).map(([k, v]) => (
                <div key={k} className="text-xs text-gray-500">{k}: {String(v)}</div>
              ))}
              {results.message && <div className="text-xs text-gray-500 mt-1">{results.message}</div>}
            </div>
            {results.convergence_history && results.convergence_history.length > 1 && (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={results.convergence_history.map((v: number, i: number) => ({ iter: i, value: v }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="iter" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 10, backgroundColor: '#1F2937', border: 'none' }} />
                    <Line type="monotone" dataKey="value" stroke="#3B82F6" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
