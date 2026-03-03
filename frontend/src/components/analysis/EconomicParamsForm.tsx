import { ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';

export interface EconomicParams {
  steamCost: number;
  cwCost: number;
  elecCost: number;
  fuelCost: number;
  carbonPrice: number;
  hoursPerYear: number;
}

export const DEFAULT_ECONOMIC_PARAMS: EconomicParams = {
  steamCost: 15.0,
  cwCost: 3.0,
  elecCost: 0.08,
  fuelCost: 8.0,
  carbonPrice: 50.0,
  hoursPerYear: 8000,
};

interface EconomicParamsFormProps {
  value: EconomicParams;
  onChange: (params: EconomicParams) => void;
  defaultCollapsed?: boolean;
}

export default function EconomicParamsForm({ value, onChange, defaultCollapsed = true }: EconomicParamsFormProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const set = (key: keyof EconomicParams, v: number) => onChange({ ...value, [key]: v });

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
      >
        Economic Parameters
        {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 grid grid-cols-3 gap-2">
          <div>
            <label className="text-[10px] text-gray-500">Steam $/GJ</label>
            <input type="number" value={value.steamCost} min={0} step={0.5} onChange={(e) => set('steamCost', Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">CW $/GJ</label>
            <input type="number" value={value.cwCost} min={0} step={0.5} onChange={(e) => set('cwCost', Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Elec $/kWh</label>
            <input type="number" value={value.elecCost} min={0} step={0.01} onChange={(e) => set('elecCost', Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Fuel $/GJ</label>
            <input type="number" value={value.fuelCost} min={0} step={0.5} onChange={(e) => set('fuelCost', Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">CO2 $/t</label>
            <input type="number" value={value.carbonPrice} min={0} step={5} onChange={(e) => set('carbonPrice', Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Hrs/yr</label>
            <input type="number" value={value.hoursPerYear} min={1} max={8760} onChange={(e) => set('hoursPerYear', Number(e.target.value))}
              className="w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1" />
          </div>
        </div>
      )}
    </div>
  );
}
