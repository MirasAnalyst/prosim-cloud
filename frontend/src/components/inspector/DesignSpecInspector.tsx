import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { EquipmentType } from '../../types';

const TARGET_PROPERTIES = [
  { value: 'temperature', label: 'Temperature (°C)' },
  { value: 'pressure', label: 'Pressure (kPa)' },
  { value: 'flowRate', label: 'Flow Rate (kg/s)' },
  { value: 'vapor_fraction', label: 'Vapor Fraction' },
];

interface DesignSpecInspectorProps {
  nodeId: string;
  parameters: Record<string, any>;
  onParamChange: (key: string, value: any) => void;
}

export default function DesignSpecInspector({ parameters, onParamChange }: DesignSpecInspectorProps) {
  const nodes = useFlowsheetStore((s) => s.nodes);

  const equipmentNodes = nodes.filter((n: any) => {
    const t = n.data?.equipmentType;
    return t && t !== 'DesignSpec' && t !== 'FeedStream' && t !== 'ProductStream';
  });

  const getParamKeys = (nid: string) => {
    const node = nodes.find((n: any) => n.id === nid);
    if (!node) return [];
    const eqType = (node as any).data?.equipmentType;
    if (!eqType || !(eqType in equipmentLibrary)) return [];
    return Object.keys(equipmentLibrary[eqType as EquipmentType].parameters);
  };

  const getName = (nid: string) => {
    const node = nodes.find((n: any) => n.id === nid);
    return (node as any)?.data?.name || nid.slice(0, 8);
  };

  const inputClass = "w-full text-xs bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 focus:outline-none focus:border-blue-500";

  return (
    <div className="space-y-3">
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Target</div>

      <div>
        <label className="text-[10px] text-gray-500">Target Equipment</label>
        <select value={parameters.targetStreamId || ''} onChange={(e) => onParamChange('targetStreamId', e.target.value)} className={inputClass}>
          <option value="">Select equipment</option>
          {equipmentNodes.map((n: any) => (
            <option key={n.id} value={n.id}>{getName(n.id)} ({n.data?.equipmentType})</option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-[10px] text-gray-500">Target Property</label>
        <select value={parameters.targetProperty || 'temperature'} onChange={(e) => onParamChange('targetProperty', e.target.value)} className={inputClass}>
          {TARGET_PROPERTIES.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-[10px] text-gray-500">Target Value</label>
        <input type="number" value={parameters.targetValue ?? 0} onChange={(e) => onParamChange('targetValue', Number(e.target.value))} className={inputClass} />
      </div>

      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider pt-2">Manipulated Variable</div>

      <div>
        <label className="text-[10px] text-gray-500">Manipulated Equipment</label>
        <select value={parameters.manipulatedNodeId || ''} onChange={(e) => onParamChange('manipulatedNodeId', e.target.value)} className={inputClass}>
          <option value="">Select equipment</option>
          {equipmentNodes.map((n: any) => (
            <option key={n.id} value={n.id}>{getName(n.id)} ({n.data?.equipmentType})</option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-[10px] text-gray-500">Manipulated Parameter</label>
        <select value={parameters.manipulatedParam || ''} onChange={(e) => onParamChange('manipulatedParam', e.target.value)} className={inputClass}>
          <option value="">Select parameter</option>
          {parameters.manipulatedNodeId && getParamKeys(parameters.manipulatedNodeId).map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
      </div>

      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider pt-2">Bounds</div>

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-[10px] text-gray-500">Lower</label>
          <input type="number" value={parameters.lowerBound ?? 0} onChange={(e) => onParamChange('lowerBound', Number(e.target.value))} className={inputClass} />
        </div>
        <div>
          <label className="text-[10px] text-gray-500">Upper</label>
          <input type="number" value={parameters.upperBound ?? 1000} onChange={(e) => onParamChange('upperBound', Number(e.target.value))} className={inputClass} />
        </div>
        <div>
          <label className="text-[10px] text-gray-500">Tolerance</label>
          <input type="number" value={parameters.tolerance ?? 0.01} step={0.001} onChange={(e) => onParamChange('tolerance', Number(e.target.value))} className={inputClass} />
        </div>
      </div>
    </div>
  );
}
