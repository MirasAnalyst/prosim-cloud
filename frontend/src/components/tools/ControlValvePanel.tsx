import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { API_BASE } from '../../lib/api-client';

interface ControlValvePanelProps {
  open: boolean;
  onClose: () => void;
}

export default function ControlValvePanel({ open, onClose }: ControlValvePanelProps) {
  const [phase, setPhase] = useState('liquid');
  const [valveType, setValveType] = useState('globe');
  const [inletP, setInletP] = useState(500);
  const [outletP, setOutletP] = useState(300);
  const [temperature, setTemperature] = useState(25);
  const [volFlow, setVolFlow] = useState(10);
  const [sg, setSg] = useState(1.0);
  const [massFlow, setMassFlow] = useState(5000);
  const [mw, setMw] = useState(28.97);
  const [kRatio] = useState(1.4);
  const [pipeDia, setPipeDia] = useState(0.1);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const run = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/simulation/control-valve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phase,
          valve_type: valveType,
          inlet_pressure: inletP,
          outlet_pressure: outletP,
          temperature,
          volumetric_flow: volFlow,
          specific_gravity: sg,
          mass_flow_rate: massFlow,
          molecular_weight: mw,
          k_ratio: kRatio,
          pipe_diameter: pipeDia,
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
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Control Valve Sizing</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Phase</label>
            <select value={phase} onChange={(e) => setPhase(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="liquid">Liquid</option>
              <option value="gas">Gas</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Valve Type</label>
            <select value={valveType} onChange={(e) => setValveType(e.target.value)}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1">
              <option value="globe">Globe</option>
              <option value="butterfly">Butterfly</option>
              <option value="ball">Ball</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Pipe Dia (m)</label>
            <input type="number" value={pipeDia} step={0.01} onChange={(e) => setPipeDia(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Inlet P (kPa)</label>
            <input type="number" value={inletP} onChange={(e) => setInletP(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Outlet P (kPa)</label>
            <input type="number" value={outletP} onChange={(e) => setOutletP(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Temp (°C)</label>
            <input type="number" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>

        {phase === 'liquid' ? (
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
        ) : (
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
          </div>
        )}

        <button onClick={run} disabled={running}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Sizing...' : 'Size Control Valve'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Results</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-600 dark:text-gray-400">
              <span>Calculated Cv:</span><span className="text-right">{results.calculated_cv}</span>
              <span>Selected Cv:</span><span className="text-right font-semibold text-blue-400">{results.selected_cv}</span>
              <span>% Open:</span><span className="text-right">{results.percent_open}%</span>
              <span>FL:</span><span className="text-right">{results.fl}</span>
              <span>xT:</span><span className="text-right">{results.xt}</span>
              <span>Flow Regime:</span><span className={`text-right ${results.choked ? 'text-red-400' : 'text-green-500'}`}>{results.flow_regime}</span>
              {results.choked && (
                <><span>Choked ΔP:</span><span className="text-right text-red-400">{results.choked_dp_kpa} kPa</span></>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
