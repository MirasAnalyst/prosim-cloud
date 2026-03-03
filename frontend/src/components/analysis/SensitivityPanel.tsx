import { useState } from 'react';
import { X, Play, Loader2, LineChart } from 'lucide-react';
import { LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { EquipmentType } from '../../types';
import { API_BASE } from '../../lib/api-client';

interface SensitivityOutput {
  nodeId: string;
  resultKey: string;
  label: string;
}

interface SensitivityResults {
  variableValues: number[];
  outputValues: Record<string, (number | null)[]>;
  variableLabel: string;
}

const RESULT_KEYS = [
  { value: 'duty', label: 'Duty (kW)' },
  { value: 'work', label: 'Work (kW)' },
  { value: 'outletTemperature', label: 'Outlet Temperature (°C)' },
  { value: 'vaporFraction', label: 'Vapor Fraction' },
  { value: 'massFlow', label: 'Mass Flow (kg/s)' },
  { value: 'outletPressure', label: 'Outlet Pressure (kPa)' },
  { value: 'pressureDrop', label: 'Pressure Drop (kPa)' },
];

const COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];

interface SensitivityPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function SensitivityPanel({ open, onClose }: SensitivityPanelProps) {
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);
  const simulationBasis = useFlowsheetStore((s) => s.simulationBasis);

  const [variableNodeId, setVariableNodeId] = useState('');
  const [variableParamKey, setVariableParamKey] = useState('');
  const [minValue, setMinValue] = useState(0);
  const [maxValue, setMaxValue] = useState(100);
  const [steps, setSteps] = useState(10);
  const [outputs, setOutputs] = useState<SensitivityOutput[]>([]);
  const [newOutputNodeId, setNewOutputNodeId] = useState('');
  const [newOutputKey, setNewOutputKey] = useState('duty');
  const [results, setResults] = useState<SensitivityResults | null>(null);
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const equipmentNodes = nodes.filter((n) => n.data.equipmentType in EquipmentType);

  const selectedNode = equipmentNodes.find((n) => n.id === variableNodeId);
  const paramKeys = selectedNode
    ? Object.keys(equipmentLibrary[selectedNode.data.equipmentType]?.parameters ?? {})
    : [];

  const addOutput = () => {
    if (!newOutputNodeId || !newOutputKey) return;
    const node = equipmentNodes.find((n) => n.id === newOutputNodeId);
    const label = `${node?.data.name ?? newOutputNodeId}.${newOutputKey}`;
    setOutputs([...outputs, { nodeId: newOutputNodeId, resultKey: newOutputKey, label }]);
  };

  const removeOutput = (index: number) => {
    setOutputs(outputs.filter((_, i) => i !== index));
  };

  const runSensitivity = async () => {
    if (!variableNodeId || !variableParamKey || outputs.length === 0) return;

    setStatus('running');
    setError(null);

    const simNodes = nodes.map((n) => ({
      id: n.id,
      type: n.data.equipmentType,
      name: n.data.name,
      parameters: { ...n.data.parameters },
      position: n.position,
    }));
    const simEdges = edges.map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? '',
      target: e.target,
      targetHandle: e.targetHandle ?? '',
      type: e.type ?? 'stream',
    }));

    try {
      const res = await fetch(`${API_BASE}/api/simulation/sensitivity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_nodes: simNodes,
          base_edges: simEdges,
          property_package: propertyPackage,
          simulation_basis: simulationBasis.compounds.length > 0 ? simulationBasis : undefined,
          variable: {
            node_id: variableNodeId,
            parameter_key: variableParamKey,
            min_value: minValue,
            max_value: maxValue,
            steps,
          },
          outputs: outputs.map((o) => ({
            node_id: o.nodeId,
            result_key: o.resultKey,
          })),
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResults({
        variableValues: data.variable_values,
        outputValues: data.output_values,
        variableLabel: data.variable_label,
      });
      setStatus('completed');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sensitivity analysis failed');
      setStatus('error');
    }
  };

  // Build chart data
  const chartData = results
    ? results.variableValues.map((x, i) => {
        const point: Record<string, number | null> = { x };
        for (const [key, values] of Object.entries(results.outputValues)) {
          point[key] = values[i];
        }
        return point;
      })
    : [];

  if (!open) return null;

  return (
    <div className="absolute right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <LineChart size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Sensitivity Analysis</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Variable Selector */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider">
            Independent Variable
          </label>
          <select
            value={variableNodeId}
            onChange={(e) => { setVariableNodeId(e.target.value); setVariableParamKey(''); }}
            className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500"
          >
            <option value="">Select equipment...</option>
            {equipmentNodes.map((n) => (
              <option key={n.id} value={n.id}>{n.data.name} ({n.data.equipmentType})</option>
            ))}
          </select>
          {variableNodeId && (
            <select
              value={variableParamKey}
              onChange={(e) => setVariableParamKey(e.target.value)}
              className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 mb-2 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500"
            >
              <option value="">Select parameter...</option>
              {paramKeys.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          )}
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">Min</label>
              <input type="number" value={minValue} onChange={(e) => setMinValue(Number(e.target.value))}
                className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" />
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">Max</label>
              <input type="number" value={maxValue} onChange={(e) => setMaxValue(Number(e.target.value))}
                className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" />
            </div>
            <div className="w-20">
              <label className="block text-xs text-gray-500 mb-1">Steps</label>
              <input type="number" value={steps} min={2} max={100} onChange={(e) => setSteps(Number(e.target.value))}
                className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500" />
            </div>
          </div>
        </div>

        {/* Output Selector */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1 font-semibold uppercase tracking-wider">
            Tracked Outputs
          </label>
          <div className="flex gap-2 mb-2">
            <select value={newOutputNodeId} onChange={(e) => setNewOutputNodeId(e.target.value)}
              className="flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-xs rounded px-2 py-1.5 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500">
              <option value="">Equipment...</option>
              {equipmentNodes.map((n) => (
                <option key={n.id} value={n.id}>{n.data.name}</option>
              ))}
            </select>
            <select value={newOutputKey} onChange={(e) => setNewOutputKey(e.target.value)}
              className="flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-xs rounded px-2 py-1.5 text-gray-700 dark:text-gray-300 focus:outline-none focus:border-blue-500">
              {RESULT_KEYS.map((rk) => (
                <option key={rk.value} value={rk.value}>{rk.label}</option>
              ))}
            </select>
            <button onClick={addOutput}
              className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500">
              Add
            </button>
          </div>
          {outputs.map((out, i) => (
            <div key={i} className="flex items-center justify-between px-2 py-1 bg-gray-50 dark:bg-gray-800/50 rounded mb-1 text-xs text-gray-700 dark:text-gray-300">
              <span className="truncate flex-1">{out.label}</span>
              <button onClick={() => removeOutput(i)} className="ml-2 text-gray-400 hover:text-red-400">
                <X size={12} />
              </button>
            </div>
          ))}
        </div>

        {/* Run Button */}
        <button
          onClick={runSensitivity}
          disabled={status === 'running' || !variableNodeId || !variableParamKey || outputs.length === 0}
          className={`w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            status === 'running'
              ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-500'
          }`}
        >
          {status === 'running' ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {status === 'running' ? 'Running...' : 'Run Sensitivity'}
        </button>

        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{error}</div>
        )}

        {/* Results Chart */}
        {results && chartData.length > 0 && (
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold uppercase tracking-wider">
              Results
            </label>
            <div className="h-64 bg-gray-50 dark:bg-gray-800/50 rounded p-2">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsLineChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis
                    dataKey="x"
                    tick={{ fontSize: 10, fill: '#9CA3AF' }}
                    label={{ value: results.variableLabel, position: 'insideBottom', offset: -2, fontSize: 10, fill: '#9CA3AF' }}
                  />
                  <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '6px', fontSize: '11px' }}
                    labelStyle={{ color: '#9CA3AF' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '10px' }} />
                  {Object.keys(results.outputValues).map((key, i) => (
                    <Line
                      key={key}
                      type="monotone"
                      dataKey={key}
                      stroke={COLORS[i % COLORS.length]}
                      strokeWidth={2}
                      dot={{ r: 2 }}
                      name={key}
                      connectNulls
                    />
                  ))}
                </RechartsLineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
