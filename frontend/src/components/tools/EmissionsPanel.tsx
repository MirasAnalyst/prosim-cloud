import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { useSimulationStore } from '../../stores/simulationStore';

interface EmissionsPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function EmissionsPanel({ open, onClose }: EmissionsPanelProps) {
  const simResults = useSimulationStore((s) => s.results);
  const [fuelType, setFuelType] = useState('natural_gas');
  const [consumption, setConsumption] = useState(0);
  const [carbonPrice, setCarbonPrice] = useState(50);
  const [hoursPerYear, setHoursPerYear] = useState(8000);
  const [valves, setValves] = useState(0);
  const [pumps, setPumps] = useState(0);
  const [compressors, setCompressors] = useState(0);
  const [flanges, setFlanges] = useState(0);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const run = async () => {
    setRunning(true);
    setError('');
    try {
      const raw = simResults ? {
        stream_results: simResults.streamResults,
        equipment_results: simResults.equipmentResults,
      } : null;
      const res = await fetch('/api/simulation/emissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          simulation_results: raw,
          fuel: { fuel_type: fuelType, consumption },
          equipment_counts: { valves, pumps, compressors, flanges },
          carbon_price: carbonPrice,
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
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Environmental Calculations</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Combustion</label>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Fuel Type</label>
              <select value={fuelType} onChange={(e) => setFuelType(e.target.value)}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
                <option value="natural_gas">Natural Gas</option>
                <option value="fuel_oil">Fuel Oil</option>
                <option value="coal">Coal</option>
                <option value="lpg">LPG</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Consumption (GJ/hr, 0=auto)</label>
              <input type="number" value={consumption} onChange={(e) => setConsumption(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Fugitive Equipment Counts</label>
          <div className="grid grid-cols-4 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Valves</label>
              <input type="number" value={valves} min={0} onChange={(e) => setValves(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Pumps</label>
              <input type="number" value={pumps} min={0} onChange={(e) => setPumps(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Compr.</label>
              <input type="number" value={compressors} min={0} onChange={(e) => setCompressors(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Flanges</label>
              <input type="number" value={flanges} min={0} onChange={(e) => setFlanges(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Carbon Price ($/t CO2e)</label>
            <input type="number" value={carbonPrice} onChange={(e) => setCarbonPrice(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Hours/Year</label>
            <input type="number" value={hoursPerYear} onChange={(e) => setHoursPerYear(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>

        <button onClick={run} disabled={running}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Computing...' : 'Calculate Emissions'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-2">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Results (tonnes/year)</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-gray-600 dark:text-gray-400">
              <span>CO2:</span><span className="text-right">{results.combustion_co2_tpy?.toFixed(1)}</span>
              <span>NOx:</span><span className="text-right">{results.combustion_nox_tpy?.toFixed(3)}</span>
              <span>SOx:</span><span className="text-right">{results.combustion_sox_tpy?.toFixed(3)}</span>
              <span>CO:</span><span className="text-right">{results.combustion_co_tpy?.toFixed(3)}</span>
              <span>PM:</span><span className="text-right">{results.combustion_pm_tpy?.toFixed(3)}</span>
              <span>Fugitive VOC:</span><span className="text-right">{results.fugitive_voc_tpy?.toFixed(3)}</span>
              <span>Fugitive CH4:</span><span className="text-right">{results.fugitive_methane_tpy?.toFixed(3)}</span>
            </div>
            <div className="border-t border-gray-200 dark:border-gray-700 pt-1">
              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Total CO2e: {results.total_co2e_tpy?.toFixed(1)} t/yr</div>
              <div className="text-xs font-semibold text-green-500">Carbon Cost: ${results.carbon_cost_annual?.toLocaleString()}/yr</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
