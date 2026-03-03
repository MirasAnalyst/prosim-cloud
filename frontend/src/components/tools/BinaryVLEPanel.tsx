import { useState } from 'react';
import { X, BarChart3 } from 'lucide-react';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { useSimulationStore } from '../../stores/simulationStore';
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

interface BinaryVLEPanelProps {
  open: boolean;
  onClose: () => void;
}

type DiagramType = 'txy' | 'pxy' | 'xy';

interface VLEResult {
  bubble_curve: Array<Record<string, number>>;
  dew_curve: Array<Record<string, number>>;
  xy_curve: Array<Record<string, number>>;
  compounds: string[];
  diagram_type: string;
  P_kPa?: number;
  T_C?: number;
}

export default function BinaryVLEPanel({ open, onClose }: BinaryVLEPanelProps) {
  const compounds = useFlowsheetStore((s) => s.simulationBasis.compounds);
  const propertyPackage = useSimulationStore((s) => s.propertyPackage);

  const [compA, setCompA] = useState('');
  const [compB, setCompB] = useState('');
  const [diagramType, setDiagramType] = useState<DiagramType>('txy');
  const [pressure, setPressure] = useState(101.325); // kPa for Txy
  const [temperature, setTemperature] = useState(25); // °C for Pxy
  const [nPoints, setNPoints] = useState(51);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VLEResult | null>(null);
  const [error, setError] = useState('');

  const canCompute = compA && compB && compA !== compB;

  const compute = async () => {
    if (!canCompute) return;
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const endpoint = diagramType === 'pxy'
        ? '/api/simulation/binary-vle/pxy'
        : '/api/simulation/binary-vle/txy';

      const body: Record<string, unknown> = {
        comp_a: compA,
        comp_b: compB,
        property_package: propertyPackage,
        n_points: nPoints,
      };

      if (diagramType === 'pxy') {
        body.T = temperature + 273.15; // °C → K
      } else {
        body.P = pressure * 1000; // kPa → Pa
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to compute VLE diagram');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="absolute right-0 top-0 h-full w-[480px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-40 flex flex-col shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <BarChart3 size={16} className="text-orange-400" />
          <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Binary VLE Diagrams</h2>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Compound selection */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Component A</label>
            <select
              value={compA}
              onChange={(e) => setCompA(e.target.value)}
              className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 text-gray-700 dark:text-gray-300"
            >
              <option value="">Select...</option>
              {compounds.map((c) => (
                <option key={c} value={c} disabled={c === compB}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Component B</label>
            <select
              value={compB}
              onChange={(e) => setCompB(e.target.value)}
              className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-sm rounded px-2 py-1.5 text-gray-700 dark:text-gray-300"
            >
              <option value="">Select...</option>
              {compounds.map((c) => (
                <option key={c} value={c} disabled={c === compA}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Diagram type */}
        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Diagram Type</label>
          <div className="flex gap-2">
            {(['txy', 'pxy', 'xy'] as DiagramType[]).map((t) => (
              <button
                key={t}
                onClick={() => setDiagramType(t)}
                className={`px-3 py-1 text-xs rounded border ${
                  diagramType === t
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-700'
                }`}
              >
                {t === 'txy' ? 'Txy' : t === 'pxy' ? 'Pxy' : 'x-y'}
              </button>
            ))}
          </div>
        </div>

        {/* Constant variable */}
        {diagramType !== 'xy' && (
          <div>
            {diagramType === 'txy' ? (
              <>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Pressure (kPa)</label>
                <input
                  type="number"
                  value={pressure}
                  onChange={(e) => setPressure(Number(e.target.value))}
                  className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300"
                />
              </>
            ) : (
              <>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Temperature (°C)</label>
                <input
                  type="number"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300"
                />
              </>
            )}
          </div>
        )}

        <div>
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Points</label>
          <input
            type="number"
            value={nPoints}
            onChange={(e) => setNPoints(Math.min(200, Math.max(11, Number(e.target.value))))}
            min={11}
            max={200}
            className="w-24 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300"
          />
        </div>

        <button
          onClick={compute}
          disabled={!canCompute || loading}
          className="w-full py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Computing...' : 'Generate Diagram'}
        </button>

        {error && (
          <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 rounded p-2">{error}</div>
        )}

        {/* Chart */}
        {result && (
          <div className="border-t border-gray-200 dark:border-gray-800 pt-4">
            {diagramType === 'xy' || (diagramType !== 'pxy' && diagramType !== 'txy' && result.xy_curve?.length > 0) ? (
              <XYDiagram data={result} compA={compA} />
            ) : diagramType === 'txy' ? (
              <TxyDiagram data={result} compA={compA} />
            ) : (
              <PxyDiagram data={result} compA={compA} />
            )}
          </div>
        )}

        {compounds.length < 2 && (
          <div className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded p-3">
            Add at least 2 compounds in the Simulation Basis panel to use binary VLE diagrams.
          </div>
        )}
      </div>
    </div>
  );
}

function TxyDiagram({ data, compA }: { data: VLEResult; compA: string }) {
  // Merge bubble and dew curves on x_a
  const merged: Array<{ x_a: number; T_bubble?: number; T_dew?: number }> = [];
  const map = new Map<number, { T_bubble?: number; T_dew?: number }>();

  for (const pt of data.bubble_curve) {
    const key = pt.x_a;
    const entry = map.get(key) || {};
    entry.T_bubble = pt.T_C;
    map.set(key, entry);
  }
  for (const pt of data.dew_curve) {
    const key = pt.x_a;
    const entry = map.get(key) || {};
    entry.T_dew = pt.T_C;
    map.set(key, entry);
  }
  for (const [x_a, vals] of Array.from(map.entries()).sort((a, b) => a[0] - b[0])) {
    merged.push({ x_a, ...vals });
  }

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
        Txy Diagram — {compA} at {data.P_kPa ?? ''} kPa
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={merged} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis dataKey="x_a" label={{ value: `x, y (${compA})`, position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
          <YAxis label={{ value: 'T (°C)', angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Line type="monotone" dataKey="T_bubble" name="Bubble" stroke="#3b82f6" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="T_dew" name="Dew" stroke="#ef4444" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PxyDiagram({ data, compA }: { data: VLEResult; compA: string }) {
  const merged: Array<{ x_a: number; P_bubble?: number; P_dew?: number }> = [];
  const map = new Map<number, { P_bubble?: number; P_dew?: number }>();

  for (const pt of data.bubble_curve) {
    const entry = map.get(pt.x_a) || {};
    entry.P_bubble = pt.P_kPa;
    map.set(pt.x_a, entry);
  }
  for (const pt of data.dew_curve) {
    const entry = map.get(pt.x_a) || {};
    entry.P_dew = pt.P_kPa;
    map.set(pt.x_a, entry);
  }
  for (const [x_a, vals] of Array.from(map.entries()).sort((a, b) => a[0] - b[0])) {
    merged.push({ x_a, ...vals });
  }

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
        Pxy Diagram — {compA} at {data.T_C ?? ''} °C
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={merged} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis dataKey="x_a" label={{ value: `x, y (${compA})`, position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
          <YAxis label={{ value: 'P (kPa)', angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Line type="monotone" dataKey="P_bubble" name="Bubble" stroke="#3b82f6" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="P_dew" name="Dew" stroke="#ef4444" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function XYDiagram({ data, compA }: { data: VLEResult; compA: string }) {
  // x-y diagram + diagonal reference line
  const xyData = data.xy_curve.map((pt) => ({
    x: pt.x_a,
    y: pt.y_a,
    diagonal: pt.x_a,
  }));

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
        x-y Diagram — {compA}
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={xyData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis dataKey="x" domain={[0, 1]} label={{ value: `x (${compA})`, position: 'insideBottom', offset: -3, fontSize: 10 }} tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 1]} label={{ value: `y (${compA})`, angle: -90, position: 'insideLeft', fontSize: 10 }} tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={{ fontSize: 11, background: '#1f2937', border: 'none', color: '#f3f4f6' }} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Line type="monotone" dataKey="y" name="VLE" stroke="#3b82f6" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="diagonal" name="y=x" stroke="#6b7280" dot={false} strokeWidth={1} strokeDasharray="5 5" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
