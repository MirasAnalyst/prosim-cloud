import { useState } from 'react';
import { X, Play, Loader2 } from 'lucide-react';
import { API_BASE } from '../../lib/api-client';

interface HydraulicsPanelProps {
  open: boolean;
  onClose: () => void;
}

export default function HydraulicsPanel({ open, onClose }: HydraulicsPanelProps) {
  const [massFlow, setMassFlow] = useState(10);
  const [density, setDensity] = useState(1000);
  const [viscosity, setViscosity] = useState(0.001);
  const [phase] = useState('liquid');
  const [length, setLength] = useState(100);
  const [diameter, setDiameter] = useState(0.1);
  const [roughness, setRoughness] = useState(0.000045);
  const [elevation, setElevation] = useState(0);
  const [elbows90, setElbows90] = useState(0);
  const [tees, setTees] = useState(0);
  const [gateValves, setGateValves] = useState(0);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState('');

  const run = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/simulation/hydraulics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mass_flow_rate: massFlow,
          density,
          viscosity,
          phase,
          length,
          diameter,
          roughness,
          elevation,
          elbows_90: elbows90,
          tees,
          gate_valves: gateValves,
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
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Pipe Hydraulics</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Fluid Properties</label>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Flow (kg/s)</label>
              <input type="number" value={massFlow} step={0.1} onChange={(e) => setMassFlow(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Density (kg/m³)</label>
              <input type="number" value={density} onChange={(e) => setDensity(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Viscosity (Pa·s)</label>
              <input type="number" value={viscosity} step={0.0001} onChange={(e) => setViscosity(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Pipe Geometry</label>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">Length (m)</label>
              <input type="number" value={length} onChange={(e) => setLength(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Diameter (m)</label>
              <input type="number" value={diameter} step={0.001} onChange={(e) => setDiameter(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Roughness (m)</label>
              <input type="number" value={roughness} step={0.00001} onChange={(e) => setRoughness(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Elevation (m)</label>
              <input type="number" value={elevation} onChange={(e) => setElevation(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 block">Fittings</label>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] text-gray-500">90° Elbows</label>
              <input type="number" value={elbows90} min={0} onChange={(e) => setElbows90(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Tees</label>
              <input type="number" value={tees} min={0} onChange={(e) => setTees(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500">Gate Valves</label>
              <input type="number" value={gateValves} min={0} onChange={(e) => setGateValves(Number(e.target.value))}
                className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
            </div>
          </div>
        </div>

        <button onClick={run} disabled={running}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Computing...' : 'Calculate Hydraulics'}
        </button>

        {error && <div className="text-xs text-red-400">{error}</div>}

        {results && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 space-y-1">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Results</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-600 dark:text-gray-400">
              <span>Total ΔP:</span><span className="text-right">{results.pressure_drop_kpa} kPa</span>
              <span>Friction ΔP:</span><span className="text-right">{results.pressure_drop_friction_kpa} kPa</span>
              <span>Elevation ΔP:</span><span className="text-right">{results.pressure_drop_elevation_kpa} kPa</span>
              <span>Fittings ΔP:</span><span className="text-right">{results.pressure_drop_fittings_kpa} kPa</span>
              <span>Velocity:</span><span className="text-right">{results.velocity_m_s} m/s</span>
              <span>Reynolds:</span><span className="text-right">{results.reynolds_number}</span>
              <span>Friction Factor:</span><span className="text-right">{results.friction_factor}</span>
              <span>Flow Regime:</span><span className="text-right">{results.flow_regime}</span>
              <span>Erosional V:</span><span className="text-right">{results.erosional_velocity_m_s} m/s</span>
              <span>V/V_e Ratio:</span><span className={`text-right ${results.erosional_ok ? 'text-green-500' : 'text-red-400'}`}>{results.erosional_ratio}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
