import { useState } from 'react';
import { X, Play, Loader2, Download } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useSimulationStore } from '../../stores/simulationStore';
import { API_BASE } from '../../lib/api-client';

interface PinchStream {
  name: string;
  supply_temp: number;
  target_temp: number;
  heat_capacity_flow: number;
  stream_type: string;
}

interface PinchPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function PinchPanel({ open, onClose }: PinchPanelProps) {
  const simResults = useSimulationStore((s) => s.results);
  const [streams, setStreams] = useState<PinchStream[]>([]);
  const [dtMin, setDtMin] = useState(10);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const addStream = () => setStreams([...streams, { name: `Stream ${streams.length + 1}`, supply_temp: 100, target_temp: 40, heat_capacity_flow: 10, stream_type: '' }]);

  const importFromSim = async () => {
    if (!simResults) return;
    try {
      await fetch(`${API_BASE}/api/simulation/pinch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ streams: [], dt_min: dtMin }),
      });
      // Just trigger auto-extraction on backend; for now, create streams from heater/cooler results
      const eqResults = simResults.equipmentResults || {};
      const autoStreams: PinchStream[] = [];
      for (const [id, data] of Object.entries(eqResults)) {
        if (!data || typeof data === 'string') continue;
        const duty = (data as any).duty;
        const tIn = (data as any).inletTemperature ?? (data as any).outletTemperature;
        const tOut = (data as any).outletTemperature;
        if (duty == null || tIn == null || tOut == null) continue;
        const d = Number(duty);
        if (Math.abs(d) < 0.01) continue;
        const dt = Math.abs(Number(tOut) - Number(tIn));
        if (dt < 0.01) continue;
        const mCp = Math.abs(d) / dt;
        autoStreams.push({
          name: (data as any).name || id.slice(0, 8),
          supply_temp: Number(tIn),
          target_temp: Number(tOut),
          heat_capacity_flow: Math.round(mCp * 100) / 100,
          stream_type: d > 0 ? 'cold' : 'hot',
        });
      }
      if (autoStreams.length > 0) setStreams(autoStreams);
    } catch { /* ignore */ }
  };

  const run = async () => {
    if (streams.length < 2) return;
    setRunning(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/simulation/pinch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ streams, dt_min: dtMin }),
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
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Pinch Analysis</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-[10px] text-gray-500">ΔT min (°C)</label>
            <input type="number" value={dtMin} min={1} max={100} onChange={(e) => setDtMin(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <button onClick={importFromSim} disabled={!simResults}
            className="self-end text-xs px-3 py-1 bg-blue-600/20 text-blue-400 rounded hover:bg-blue-600/30 disabled:opacity-50">
            <Download size={12} className="inline mr-1" />Import from Sim
          </button>
          <button onClick={addStream} className="self-end text-xs px-3 py-1 bg-gray-600/20 text-gray-400 rounded hover:bg-gray-600/30">+ Add</button>
        </div>

        <div className="space-y-1">
          <div className="grid grid-cols-[1fr_60px_60px_60px_50px_20px] gap-1 text-[10px] text-gray-500 font-medium">
            <span>Name</span><span>T_s °C</span><span>T_t °C</span><span>mCp</span><span>Type</span><span></span>
          </div>
          {streams.map((s, i) => (
            <div key={i} className="grid grid-cols-[1fr_60px_60px_60px_50px_20px] gap-1">
              <input value={s.name} onChange={(e) => { const ss = [...streams]; ss[i].name = e.target.value; setStreams(ss); }}
                className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <input type="number" value={s.supply_temp} onChange={(e) => { const ss = [...streams]; ss[i].supply_temp = Number(e.target.value); setStreams(ss); }}
                className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <input type="number" value={s.target_temp} onChange={(e) => { const ss = [...streams]; ss[i].target_temp = Number(e.target.value); setStreams(ss); }}
                className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <input type="number" value={s.heat_capacity_flow} onChange={(e) => { const ss = [...streams]; ss[i].heat_capacity_flow = Number(e.target.value); setStreams(ss); }}
                className="text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-1 py-0.5" />
              <select value={s.stream_type} onChange={(e) => { const ss = [...streams]; ss[i].stream_type = e.target.value; setStreams(ss); }}
                className="text-[10px] bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-0.5 py-0.5">
                <option value="">Auto</option>
                <option value="hot">Hot</option>
                <option value="cold">Cold</option>
              </select>
              <button onClick={() => setStreams(streams.filter((_, j) => j !== i))} className="text-red-400 text-xs">×</button>
            </div>
          ))}
        </div>

        <button onClick={run} disabled={running || streams.length < 2}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Analyzing...' : 'Run Pinch Analysis'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="space-y-3">
            <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Results</div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Pinch Temperature: {results.pinch_temperature ?? 'N/A'} °C</div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Min Heating: {results.q_heating_min?.toFixed(1)} kW</div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Min Cooling: {results.q_cooling_min?.toFixed(1)} kW</div>
            </div>

            {(results.hot_composite?.length > 0 || results.cold_composite?.length > 0) && (
              <div className="h-52">
                <div className="text-xs font-medium text-gray-500 mb-1">Composite Curves</div>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="enthalpy" type="number" tick={{ fontSize: 9 }} label={{ value: 'H (kW)', position: 'bottom', fontSize: 9 }} />
                    <YAxis dataKey="temperature" type="number" tick={{ fontSize: 9 }} label={{ value: 'T (°C)', angle: -90, position: 'left', fontSize: 9 }} />
                    <Tooltip contentStyle={{ fontSize: 10, backgroundColor: '#1F2937', border: 'none' }} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    {results.hot_composite?.length > 0 && (
                      <Line data={results.hot_composite} dataKey="temperature" stroke="#EF4444" dot={false} name="Hot" />
                    )}
                    {results.cold_composite?.length > 0 && (
                      <Line data={results.cold_composite} dataKey="temperature" stroke="#3B82F6" dot={false} name="Cold" />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {results.grand_composite?.length > 0 && (
              <div className="h-48">
                <div className="text-xs font-medium text-gray-500 mb-1">Grand Composite</div>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={results.grand_composite}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="enthalpy" tick={{ fontSize: 9 }} />
                    <YAxis dataKey="temperature" tick={{ fontSize: 9 }} />
                    <Tooltip contentStyle={{ fontSize: 10, backgroundColor: '#1F2937', border: 'none' }} />
                    <Line type="monotone" dataKey="temperature" stroke="#10B981" dot={false} />
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
