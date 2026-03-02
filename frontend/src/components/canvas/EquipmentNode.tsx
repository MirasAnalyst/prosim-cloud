import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { EquipmentNodeData } from '../../stores/flowsheetStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { EquipmentIcon, getNodeDimensions } from './EquipmentIcons';
import { useSimulationStore } from '../../stores/simulationStore';
import { SimulationStatus, EquipmentType } from '../../types';

function getResultBadge(
  equipmentType: EquipmentType,
  eqResult: Record<string, number | string>
): string | null {
  switch (equipmentType) {
    case EquipmentType.Heater:
    case EquipmentType.Cooler:
    case EquipmentType.HeatExchanger: {
      const duty = eqResult.duty;
      if (duty == null) return null;
      const label = `Q: ${Number(duty).toFixed(1)} kW`;
      if (equipmentType === EquipmentType.HeatExchanger && eqResult.LMTD != null) {
        return `${label} | LMTD: ${Number(eqResult.LMTD).toFixed(1)}°C`;
      }
      return label;
    }
    case EquipmentType.Pump:
    case EquipmentType.Compressor: {
      const work = eqResult.work;
      if (work == null) return null;
      return `W: ${Number(work).toFixed(1)} kW`;
    }
    case EquipmentType.Separator: {
      const vf = eqResult.vaporFraction ?? eqResult.vapor_fraction;
      if (vf == null) return null;
      return `VF: ${Number(vf).toFixed(3)}`;
    }
    case EquipmentType.DistillationColumn: {
      const lkPurity = eqResult.lightKeyPurity;
      if (lkPurity != null) return `LK: ${Number(lkPurity).toFixed(1)}%`;
      const stages = eqResult.numberOfStages;
      if (stages != null) return `${stages} stages`;
      return null;
    }
    case EquipmentType.ConversionReactor: {
      const conv = eqResult.conversion;
      if (conv == null) return null;
      return `X: ${Number(conv).toFixed(1)}%`;
    }
    case EquipmentType.Splitter: {
      const ratio = eqResult.splitRatio;
      if (ratio == null) return null;
      const r = Number(ratio);
      return `${(r * 100).toFixed(0)}/${((1 - r) * 100).toFixed(0)}`;
    }
    case EquipmentType.Mixer: {
      const flow = eqResult.totalMassFlow;
      if (flow == null) return null;
      return `${Number(flow).toFixed(2)} kg/s`;
    }
    case EquipmentType.Valve: {
      const cv = eqResult.calculatedCv;
      if (cv != null && Number(cv) > 0) {
        return `Cv: ${Number(cv).toFixed(1)} | ${Number(eqResult.percentOpen ?? 0).toFixed(0)}% open`;
      }
      const dp = eqResult.pressureDrop;
      if (dp == null) return null;
      return `ΔP: ${Number(dp).toFixed(1)} kPa`;
    }
    case EquipmentType.Absorber:
    case EquipmentType.Stripper: {
      const stages = eqResult.numberOfStages;
      if (stages != null) return `${stages} stages`;
      return null;
    }
    case EquipmentType.Cyclone: {
      const dp = eqResult.pressureDrop;
      if (dp == null) return null;
      return `ΔP: ${Number(dp).toFixed(1)} kPa`;
    }
    case EquipmentType.ThreePhaseSeparator: {
      const vf = eqResult.vaporFraction;
      if (vf == null) return null;
      return `VF: ${Number(vf).toFixed(3)}`;
    }
    case EquipmentType.Crystallizer: {
      const cy = eqResult.crystalYield;
      if (cy == null) return null;
      return `Yield: ${Number(cy).toFixed(1)}%`;
    }
    case EquipmentType.Dryer: {
      const moist = eqResult.outletMoisture;
      if (moist == null) return null;
      return `${Number(moist).toFixed(1)}% moisture`;
    }
    case EquipmentType.Filter: {
      const eff = eqResult.efficiency;
      if (eff == null) return null;
      return `Eff: ${Number(eff).toFixed(1)}%`;
    }
    case EquipmentType.DesignSpec: {
      const conv = eqResult.converged;
      const achieved = eqResult.achievedValue;
      if (conv != null) {
        const status = conv ? 'OK' : 'FAIL';
        return achieved != null ? `${status} (${Number(achieved).toFixed(2)})` : status;
      }
      return null;
    }
    case EquipmentType.PipeSegment: {
      const dpPipe = eqResult.pressureDrop;
      const vel = eqResult.velocity;
      if (dpPipe == null) return null;
      const parts = [`ΔP: ${Number(dpPipe).toFixed(2)} kPa`];
      if (vel != null) parts.push(`V: ${Number(vel).toFixed(2)} m/s`);
      return parts.join(' | ');
    }
    case EquipmentType.FeedStream: {
      const t = eqResult.outletTemperature;
      const p = eqResult.outletPressure;
      const f = eqResult.massFlow;
      if (t == null && p == null && f == null) return null;
      const parts: string[] = [];
      if (t != null) parts.push(`${Number(t).toFixed(1)}°C`);
      if (p != null) parts.push(`${Number(p).toFixed(1)} kPa`);
      if (f != null) parts.push(`${Number(f).toFixed(3)} kg/s`);
      return parts.join(' | ');
    }
    case EquipmentType.ProductStream: {
      const t = eqResult.outletTemperature;
      const p = eqResult.outletPressure;
      const f = eqResult.massFlow;
      const vf = eqResult.vaporFraction;
      if (t == null && p == null && f == null) return null;
      const parts: string[] = [];
      if (t != null) parts.push(`${Number(t).toFixed(1)}°C`);
      if (p != null) parts.push(`${Number(p).toFixed(1)} kPa`);
      if (f != null) parts.push(`${Number(f).toFixed(3)} kg/s`);
      if (vf != null) parts.push(`VF: ${Number(vf).toFixed(3)}`);
      return parts.join(' | ');
    }
    default:
      return null;
  }
}

function EquipmentNode({ id, data, selected }: NodeProps) {
  const nodeData = data as unknown as EquipmentNodeData;
  const def = equipmentLibrary[nodeData.equipmentType];
  const dims = getNodeDimensions(nodeData.equipmentType);

  const results = useSimulationStore((s) => s.results);
  const status = useSimulationStore((s) => s.status);

  const eqResult =
    status === SimulationStatus.Completed && results?.equipmentResults
      ? results.equipmentResults[id]
      : null;

  const badge = eqResult
    ? getResultBadge(nodeData.equipmentType, eqResult)
    : null;

  const isEnergy = (portId: string) => portId.startsWith('energy');
  const leftPorts = def.ports.filter((p) => p.position === 'left' && !isEnergy(p.id));
  const rightPorts = def.ports.filter((p) => p.position === 'right' && !isEnergy(p.id));
  const topPorts = def.ports.filter((p) => p.position === 'top' && !isEnergy(p.id));
  const bottomPorts = def.ports.filter((p) => p.position === 'bottom' && !isEnergy(p.id));
  const energyPorts = def.ports.filter((p) => isEnergy(p.id));

  return (
    <div
      className="relative flex items-center justify-center"
      style={{
        width: dims.width,
        height: dims.height,
        filter: selected
          ? 'drop-shadow(0 0 6px rgba(59, 130, 246, 0.5))'
          : 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))',
      }}
    >
      {topPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type={port.type === 'inlet' ? 'target' : 'source'}
          position={Position.Top}
          className="!w-3 !h-3 !bg-white !border-2 !border-gray-500 hover:!bg-blue-400"
          style={{
            left: `${((i + 1) / (topPorts.length + 1)) * 100}%`,
          }}
          title={port.name}
        />
      ))}

      {leftPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type={port.type === 'inlet' ? 'target' : 'source'}
          position={Position.Left}
          className="!w-3 !h-3 !bg-white !border-2 !border-gray-500 hover:!bg-blue-400"
          style={{
            top: `${((i + 1) / (leftPorts.length + 1)) * 100}%`,
          }}
          title={port.name}
        />
      ))}

      <EquipmentIcon
        type={nodeData.equipmentType}
        width={dims.width}
        height={dims.height}
        selected={selected}
      />

      {/* Equipment name label below the shape */}
      <span
        className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] text-gray-500 dark:text-gray-400 font-medium"
        style={{ top: dims.height + 4 }}
      >
        {nodeData.name}
      </span>

      {/* Result badge below the name */}
      {badge && (
        <span
          className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[9px] text-green-400 font-mono"
          style={{ top: dims.height + 18 }}
        >
          {badge}
        </span>
      )}

      {/* Skeleton badge placeholder when simulation is running */}
      {status === SimulationStatus.Running && (
        <div
          className="absolute left-1/2 -translate-x-1/2"
          style={{ top: dims.height + 18 }}
        >
          <div className="animate-pulse bg-gray-600 rounded-full h-4 w-12" />
        </div>
      )}

      {rightPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type={port.type === 'inlet' ? 'target' : 'source'}
          position={Position.Right}
          className="!w-3 !h-3 !bg-white !border-2 !border-gray-500 hover:!bg-blue-400"
          style={{
            top: `${((i + 1) / (rightPorts.length + 1)) * 100}%`,
          }}
          title={port.name}
        />
      ))}

      {bottomPorts.map((port, i) => (
        <Handle
          key={port.id}
          id={port.id}
          type={port.type === 'inlet' ? 'target' : 'source'}
          position={Position.Bottom}
          className="!w-3 !h-3 !bg-white !border-2 !border-gray-500 hover:!bg-blue-400"
          style={{
            left: `${((i + 1) / (bottomPorts.length + 1)) * 100}%`,
          }}
          title={port.name}
        />
      ))}

      {/* Energy ports — smaller, orange handles */}
      {energyPorts.map((port) => {
        const pos = port.position === 'top' ? Position.Top : Position.Bottom;
        const samePosPorts = energyPorts.filter(p => p.position === port.position);
        const idxInPos = samePosPorts.indexOf(port);
        const style = port.position === 'top' || port.position === 'bottom'
          ? { left: `${((idxInPos + 1) / (samePosPorts.length + 1)) * 100 + (port.position === 'bottom' && bottomPorts.length > 0 ? 30 : 0)}%` }
          : {};
        return (
          <Handle
            key={port.id}
            id={port.id}
            type={port.type === 'inlet' ? 'target' : 'source'}
            position={pos}
            className="!w-2.5 !h-2.5 !bg-orange-200 !border-2 !border-orange-500 hover:!bg-orange-400"
            style={style}
            title={`⚡ ${port.name}`}
          />
        );
      })}
    </div>
  );
}

export default memo(EquipmentNode);
