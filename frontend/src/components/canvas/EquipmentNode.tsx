import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { EquipmentNodeData } from '../../stores/flowsheetStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { EquipmentIcon, getNodeDimensions } from './EquipmentIcons';

function EquipmentNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as EquipmentNodeData;
  const def = equipmentLibrary[nodeData.equipmentType];
  const dims = getNodeDimensions(nodeData.equipmentType);

  const leftPorts = def.ports.filter((p) => p.position === 'left');
  const rightPorts = def.ports.filter((p) => p.position === 'right');
  const topPorts = def.ports.filter((p) => p.position === 'top');
  const bottomPorts = def.ports.filter((p) => p.position === 'bottom');

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
        className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] text-gray-400 font-medium"
        style={{ top: dims.height + 4 }}
      >
        {nodeData.name}
      </span>

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
    </div>
  );
}

export default memo(EquipmentNode);
