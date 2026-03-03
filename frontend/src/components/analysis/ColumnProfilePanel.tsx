import { useState } from 'react';
import { X, BarChart3 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface ColumnProfilePanelProps {
  open: boolean;
  onClose: () => void;
}

type ProfileView = 'temperature' | 'composition' | 'flows';

interface StageProfile {
  stage: number;
  T_C: number;
  T_K: number;
  L: number;
  V: number;
  x: Record<string, number>;
  y: Record<string, number>;
  K: Record<string, number>;
}

export default function ColumnProfilePanel({ open, onClose }: ColumnProfilePanelProps) {
  const [view, setView] = useState<ProfileView>('temperature');
  const [selectedColumn, setSelectedColumn] = useState<string>('');

  const results = useSimulationStore((s) => s.results);
  const nodes = useFlowsheetStore((s) => s.nodes);

  // Find distillation columns with stage profiles
  const columns = nodes.filter(
    (n) => n.data.equipmentType === 'DistillationColumn'
  );

  const columnId = selectedColumn || columns[0]?.id || '';
  const eqResult = results?.equipmentResults?.[columnId];
  const stageProfiles: StageProfile[] = eqResult?.stage_profiles as unknown as StageProfile[] || [];
  const hasProfiles = stageProfiles.length > 0;

  if (!open) return null;

  // Get compound names from first stage
  const compoundNames = hasProfiles
    ? Object.keys(stageProfiles[0]?.x || {})
    : [];

  // Color palette for compounds
  const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

  return (
    <div className="absolute right-0 top-0 h-full w-[520px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <BarChart3 size={16} className="text-teal-400" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Column Profiles</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {columns.length === 0 && (
          <div className="text-xs text-gray-500 dark:text-gray-400 italic py-4 text-center">
            No distillation columns in flowsheet. Add a DistillationColumn and run simulation with rigorous method.
          </div>
        )}

        {columns.length > 1 && (
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Column</label>
            <select
              value={columnId}
              onChange={(e) => setSelectedColumn(e.target.value)}
              className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 text-gray-700 dark:text-gray-300"
            >
              {columns.map((col) => (
                <option key={col.id} value={col.id}>{col.data.name}</option>
              ))}
            </select>
          </div>
        )}

        {!hasProfiles && columnId && (
          <div className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded p-3">
            No stage profiles available. Run simulation with the &quot;Rigorous&quot; distillation method to generate profiles.
          </div>
        )}

        {hasProfiles && (
          <>
            {/* Summary */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-2">
                <span className="text-gray-500 dark:text-gray-400">Stages:</span>{' '}
                <span className="font-mono text-gray-900 dark:text-gray-100">{stageProfiles.length}</span>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-2">
                <span className="text-gray-500 dark:text-gray-400">Method:</span>{' '}
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {eqResult?.method ?? 'Rigorous'}
                </span>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-2">
                <span className="text-gray-500 dark:text-gray-400">Top T:</span>{' '}
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {stageProfiles[0]?.T_C?.toFixed(1)} °C
                </span>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800/50 rounded p-2">
                <span className="text-gray-500 dark:text-gray-400">Bottom T:</span>{' '}
                <span className="font-mono text-gray-900 dark:text-gray-100">
                  {stageProfiles[stageProfiles.length - 1]?.T_C?.toFixed(1)} °C
                </span>
              </div>
            </div>

            {/* View selector */}
            <div className="flex gap-2">
              {(['temperature', 'composition', 'flows'] as ProfileView[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={`px-3 py-1 text-xs rounded border capitalize ${
                    view === v
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-700'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>

            {/* Charts */}
            {view === 'temperature' && (
              <div>
                <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Temperature Profile</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={stageProfiles} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                    <XAxis dataKey="stage" label={{ value: 'Stage', position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
                    <YAxis label={{ value: 'T (°C)', angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
                    <Line type="monotone" dataKey="T_C" name="Temperature" stroke="#ef4444" dot={{ r: 2 }} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {view === 'composition' && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Liquid Composition (x)</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={stageProfiles.map((s) => ({ stage: s.stage, ...s.x }))} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                      <XAxis dataKey="stage" label={{ value: 'Stage', position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 1]} label={{ value: 'x', angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      {compoundNames.map((name, idx) => (
                        <Line key={name} type="monotone" dataKey={name} stroke={colors[idx % colors.length]} dot={false} strokeWidth={1.5} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Vapor Composition (y)</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={stageProfiles.map((s) => ({ stage: s.stage, ...s.y }))} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                      <XAxis dataKey="stage" label={{ value: 'Stage', position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
                      <YAxis domain={[0, 1]} label={{ value: 'y', angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      {compoundNames.map((name, idx) => (
                        <Line key={name} type="monotone" dataKey={name} stroke={colors[idx % colors.length]} dot={false} strokeWidth={1.5} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {view === 'flows' && (
              <div>
                <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Flow Rates (L/V)</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={stageProfiles} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                    <XAxis dataKey="stage" label={{ value: 'Stage', position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
                    <YAxis label={{ value: 'Flow (mol/s)', angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <Line type="monotone" dataKey="L" name="Liquid" stroke="#3b82f6" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="V" name="Vapor" stroke="#ef4444" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Stage data table */}
            <div className="border-t border-gray-200 dark:border-gray-800 pt-3">
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                Stage Data
              </h3>
              <div className="overflow-x-auto max-h-60">
                <table className="w-full text-[10px]">
                  <thead className="sticky top-0 bg-white dark:bg-gray-900">
                    <tr className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                      <th className="text-left py-1 pr-2">Stage</th>
                      <th className="text-right py-1 px-1">T (°C)</th>
                      <th className="text-right py-1 px-1">L</th>
                      <th className="text-right py-1 px-1">V</th>
                      {compoundNames.slice(0, 3).map((name) => (
                        <th key={name} className="text-right py-1 pl-1" title={name}>
                          x_{name.slice(0, 4)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stageProfiles.map((s) => (
                      <tr key={s.stage} className="border-b border-gray-100 dark:border-gray-800/50">
                        <td className="py-0.5 pr-2 text-gray-600 dark:text-gray-400">{s.stage}</td>
                        <td className="py-0.5 px-1 text-right font-mono">{s.T_C?.toFixed(1)}</td>
                        <td className="py-0.5 px-1 text-right font-mono">{s.L?.toFixed(3)}</td>
                        <td className="py-0.5 px-1 text-right font-mono">{s.V?.toFixed(3)}</td>
                        {compoundNames.slice(0, 3).map((name) => (
                          <td key={name} className="py-0.5 pl-1 text-right font-mono">
                            {s.x?.[name]?.toFixed(4)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
