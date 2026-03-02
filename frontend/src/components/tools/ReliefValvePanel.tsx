import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';

interface ReliefValvePanelProps {
  open: boolean;
  onClose: () => void;
}

export default function ReliefValvePanel({ open, onClose }: ReliefValvePanelProps) {
  const [phase, setPhase] = useState('gas');
  const [scenario, setScenario] = useState('blocked_outlet');
  const [setPressure, setSetPressure] = useState(1000);
  const [backpressure, setBackpressure] = useState(101.325);
  const [overpressure, setOverpressure] = useState(10);
  const [massFlow, setMassFlow] = useState(5000);
  const [mw, setMw] = useState(28.97);
  const [temperature, setTemperature] = useState(25);
  const [kRatio, setKRatio] = useState(1.4);
  const [volFlow, setVolFlow] = useState(10);
  const [sg, setSg] = useState(1.0);
  const [wettedArea, setWettedArea] = useState(50);
  const [insulFactor, setInsulFactor] = useState(1.0);
  const [latentHeat, setLatentHeat] = useState(200);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const run = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await fetch('/api/simulation/relief-valve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phase, scenario,
          set_pressure: setPressure,
          backpressure,
          overpressure_pct: overpressure,
          mass_flow_rate: massFlow,
          molecular_weight: mw,
          temperature,
          k_ratio: kRatio,
          volumetric_flow: volFlow,
          specific_gravity: sg,
          wetted_area: wettedArea,
          insulation_factor: insulFactor,
          latent_heat: latentHeat,
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
    <div className="fixed right-0 top-12 bottom-0 w-[420px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Relief Valve Sizing</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Phase</label>
            <select value={phase} onChange={(e) => setPhase(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="gas">Gas</option>
              <option value="liquid">Liquid</option>
              <option value="two_phase">Two-Phase</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Scenario</label>
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="blocked_outlet">Blocked Outlet</option>
              <option value="fire">Fire Case</option>
              <option value="thermal_expansion">Thermal Expansion</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Set P (kPa)</label>
            <input type="number" value={setPressure} onChange={(e) => setSetPressure(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Back P (kPa)</label>
            <input type="number" value={backpressure} onChange={(e) => setBackpressure(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Overpress %</label>
            <input type="number" value={overpressure} onChange={(e) => setOverpressure(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>

        {(phase === 'gas' || phase === 'two_phase') && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Mass Flow (kg/hr)</label>
              <input type="number" value={massFlow} onChange={(e) => setMassFlow(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">MW (g/mol)</label>
              <input type="number" value={mw} onChange={(e) => setMw(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Temperature (°C)</label>
              <input type="number" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">k (Cp/Cv)</label>
              <input type="number" value={kRatio} step={0.01} onChange={(e) => setKRatio(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        )}

        {phase === 'liquid' && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Vol Flow (m³/hr)</label>
              <input type="number" value={volFlow} onChange={(e) => setVolFlow(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Specific Gravity</label>
              <input type="number" value={sg} step={0.01} onChange={(e) => setSg(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        )}

        {scenario === 'fire' && (
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Wetted Area (m²)</label>
              <input type="number" value={wettedArea} onChange={(e) => setWettedArea(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Insulation F</label>
              <input type="number" value={insulFactor} step={0.1} onChange={(e) => setInsulFactor(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Latent Heat (kJ/kg)</label>
              <input type="number" value={latentHeat} onChange={(e) => setLatentHeat(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        )}

        <button onClick={run} disabled={running}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Sizing...' : 'Size Relief Valve'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Results</div>
            <div className="text-xs text-gray-600 dark:text-gray-400">Required Area: {results.required_area_mm2} mm² ({results.required_area_in2} in²)</div>
            <div className="text-xs font-semibold text-blue-400">Selected Orifice: {results.selected_orifice} ({results.orifice_area_mm2} mm²)</div>
            <div className="text-xs text-gray-600 dark:text-gray-400">Relieving Pressure: {results.relieving_pressure_kpa} kPa</div>
            <div className="text-xs text-gray-600 dark:text-gray-400">Mass Flow: {results.mass_flow_kg_hr} kg/hr</div>
            <div className="text-[10px] text-yellow-500 mt-2">{results.disclaimer}</div>
          </div>
        )}
      </div>
    </div>
  );
}
