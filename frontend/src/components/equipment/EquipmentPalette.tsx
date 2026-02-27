import { type DragEvent, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { equipmentByCategory } from '../../lib/equipment-library';
import { EquipmentCategory, type EquipmentType } from '../../types';
import { EquipmentIcon, getPaletteIconDimensions } from '../canvas/EquipmentIcons';

const categoryOrder: EquipmentCategory[] = [
  EquipmentCategory.Mixing,
  EquipmentCategory.HeatTransfer,
  EquipmentCategory.Separation,
  EquipmentCategory.PressureChange,
  EquipmentCategory.Reaction,
];

export default function EquipmentPalette() {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(
    Object.fromEntries(categoryOrder.map((c) => [c, true]))
  );

  const toggle = (cat: EquipmentCategory) => {
    setExpanded((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  const onDragStart = (event: DragEvent, type: EquipmentType) => {
    event.dataTransfer.setData('application/equipment-type', type);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">
          Equipment
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {categoryOrder.map((category) => (
          <div key={category}>
            <button
              onClick={() => toggle(category)}
              className="w-full flex items-center gap-2 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-gray-400 hover:bg-gray-800/50 transition-colors"
            >
              {expanded[category] ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
              <span className="text-gray-400">{category}</span>
            </button>
            {expanded[category] && (
              <div className="pb-1">
                {equipmentByCategory[category].map((eq) => {
                  const iconDims = getPaletteIconDimensions(eq.type);
                  return (
                    <div
                      key={eq.type}
                      draggable
                      onDragStart={(e) => onDragStart(e, eq.type)}
                      className="flex items-center gap-3 mx-2 px-3 py-2 rounded-md cursor-grab active:cursor-grabbing hover:bg-gray-800 transition-colors group"
                    >
                      <div className="flex items-center justify-center w-6 h-6 shrink-0">
                        <EquipmentIcon
                          type={eq.type}
                          width={iconDims.width}
                          height={iconDims.height}
                        />
                      </div>
                      <span className="text-sm text-gray-300 group-hover:text-gray-100">
                        {eq.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
