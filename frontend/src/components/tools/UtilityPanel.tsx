import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';

interface UtilityPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function UtilityPanel({ open, onClose }: UtilityPanelProps) {
  const simResults = useSimulationStore((s) => s.results);
  const [steamCost, setSteamCost] = useState(15.0);
  const [cwCost, setCwCost] = useState(3.0);
  const [elecCost, setElecCost] = useState(0.08);
  const [hoursPerYear, setHoursPerYear] = useState(8000);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const run = async () => {
    if (!simResults) return;
    setRunning(true);
    setError('');
    try {
      const raw: any = {
        stream_results: simResults.streamResults,
        equipment_results: simResults.equipmentResults,
      };
      const res = await fetch('/api/simulation/utility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          simulation_results: raw,
          costs: { steam_cost: steamCost, cooling_water_cost: cwCost, electricity_cost: elecCost },
          hours_per_year: hoursPerYear,
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
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Utility Summary</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Steam ($/GJ)</label>
            <input type="number" value={steamCost} step={0.5} onChange={(e) => setSteamCost(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">CW ($/GJ)</label>
            <input type="number" value={cwCost} step={0.5} onChange={(e) => setCwCost(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Electricity ($/kWh)</label>
            <input type="number" value={elecCost} step={0.01} onChange={(e) => setElecCost(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Hours/Year</label>
            <input type="number" value={hoursPerYear} onChange={(e) => setHoursPerYear(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>

        <button onClick={run} disabled={running || !simResults}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Computing...' : 'Compute Utilities'}
        </button>

        {!simResults && <div className="text-xs text-yellow-500">Run a simulation first to compute utility costs.</div>}
        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="space-y-3">
            <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Totals</div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Heating: {results.total_heating_kw} kW</div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Cooling: {results.total_cooling_kw} kW</div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Power: {results.total_power_kw} kW</div>
              <div className="text-xs font-semibold text-green-500 mt-1">Annual: ${results.total_annual_cost?.toLocaleString()}</div>
            </div>

            {results.equipment_utilities?.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">Equipment Breakdown</div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-1">Equipment</th>
                      <th className="text-left py-1">Utility</th>
                      <th className="text-right py-1">kW</th>
                      <th className="text-right py-1">$/yr</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.equipment_utilities.map((eu: any, i: number) => (
                      <tr key={i} className="text-gray-600 dark:text-gray-400 border-b border-gray-200/50 dark:border-gray-700/50">
                        <td className="py-0.5 truncate max-w-[120px]">{eu.equipment_name}</td>
                        <td className="py-0.5">{eu.utility_type}</td>
                        <td className="py-0.5 text-right">{eu.consumption_kw}</td>
                        <td className="py-0.5 text-right">{eu.annual_cost?.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
