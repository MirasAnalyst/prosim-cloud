import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
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

const COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];

interface DynamicPanelProps {
  open: boolean;
  onClose: () => void;
}

interface TrackedOutput {
  nodeId: string;
  resultKey: string;
  label: string;
}

interface Disturbance {
  nodeId: string;
  parameterKey: string;
  stepSize: number;
}

export default function DynamicPanel({ open, onClose }: DynamicPanelProps) {
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);
  const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);

  const [disturbance, setDisturbance] = useState<Disturbance>({ nodeId: '', parameterKey: '', stepSize: 10 });
  const [outputs, setOutputs] = useState<TrackedOutput[]>([]);
  const [timeHorizon, setTimeHorizon] = useState(3600);
  const [timeSteps, setTimeSteps] = useState(50);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<{ time: number; [key: string]: number | null }[] | null>(null);
  const [error, setError] = useState('');
  const [newOutNodeId, setNewOutNodeId] = useState('');
  const [newOutKey, setNewOutKey] = useState('');

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

  const addOutput = () => {
    if (!newOutNodeId || !newOutKey) return;
    const node = nodes.find((n: any) => n.id === newOutNodeId);
    const name = (node as any)?.data?.name || newOutNodeId.slice(0, 8);
    setOutputs([...outputs, { nodeId: newOutNodeId, resultKey: newOutKey, label: `${name}.${newOutKey}` }]);
    setNewOutNodeId('');
    setNewOutKey('');
  };

  const run = async () => {
    if (!disturbance.nodeId || !disturbance.parameterKey || outputs.length === 0) return;
    setRunning(true);
    setError('');
    try {
      const res = await fetch('/api/simulation/dynamic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_nodes: nodes,
          base_edges: edges.map((e: any) => ({ ...e, type: e.type ?? 'stream' })),
          property_package: propertyPackage,
          simulation_basis: simulationBasis,
          disturbances: [{ node_id: disturbance.nodeId, parameter_key: disturbance.parameterKey, step_size: disturbance.stepSize }],
          tracked_outputs: outputs.map((o) => ({ node_id: o.nodeId, result_key: o.resultKey, label: o.label })),
          time_horizon: timeHorizon,
          time_steps: timeSteps,
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        const chartData = (data.time_values || []).map((t: number, i: number) => {
          const row: any = { time: t };
          for (const [key, vals] of Object.entries(data.output_trajectories || {})) {
            row[key] = (vals as any[])[i];
          }
          return row;
        });
        setResults(chartData);
      }
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
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Dynamic Simulation</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Disturbance</label>
          <select value={disturbance.nodeId} onChange={(e) => setDisturbance({ ...disturbance, nodeId: e.target.value })}
            className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 mb-1">
            <option value="">Select equipment</option>
            {equipmentNodes.map((n: any) => <option key={n.id} value={n.id}>{n.data?.name || n.id.slice(0, 8)}</option>)}
          </select>
          {disturbance.nodeId && (
            <select value={disturbance.parameterKey} onChange={(e) => setDisturbance({ ...disturbance, parameterKey: e.target.value })}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 mb-1">
              <option value="">Select parameter</option>
              {getParamKeys(disturbance.nodeId).map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          )}
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[10px] text-gray-500">Step Size</label>
              <input type="number" value={disturbance.stepSize} onChange={(e) => setDisturbance({ ...disturbance, stepSize: Number(e.target.value) })}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div className="flex-1">
              <label className="text-[10px] text-gray-500">Time (s)</label>
              <input type="number" value={timeHorizon} onChange={(e) => setTimeHorizon(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div className="flex-1">
              <label className="text-[10px] text-gray-500">Steps</label>
              <input type="number" value={timeSteps} onChange={(e) => setTimeSteps(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Tracked Outputs</label>
          {outputs.map((o, i) => (
            <div key={i} className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 mb-1">
              <span className="flex-1 truncate">{o.label}</span>
              <button onClick={() => setOutputs(outputs.filter((_, j) => j !== i))} className="text-red-400 hover:text-red-600">×</button>
            </div>
          ))}
          <div className="flex gap-1">
            <select value={newOutNodeId} onChange={(e) => setNewOutNodeId(e.target.value)}
              className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="">Equipment</option>
              {equipmentNodes.map((n: any) => <option key={n.id} value={n.id}>{n.data?.name || n.id.slice(0, 8)}</option>)}
            </select>
            <select value={newOutKey} onChange={(e) => setNewOutKey(e.target.value)}
              className="flex-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="">Result key</option>
              {RESULT_KEYS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
            <button onClick={addOutput} className="text-xs text-blue-500 hover:text-blue-400">Add</button>
          </div>
        </div>

        <button onClick={run} disabled={running}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Running...' : 'Run Dynamic'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && results.length > 0 && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={results}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} label={{ value: 'Time (s)', position: 'bottom', fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ fontSize: 10, backgroundColor: '#1F2937', border: 'none' }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                {outputs.map((o, i) => {
                  const key = `${o.nodeId}.${o.resultKey}`;
                  return <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} dot={false} name={o.label} />;
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
