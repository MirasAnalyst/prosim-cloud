import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { equipmentByCategory } from '../../lib/equipment-library';
import { EquipmentCategory } from '../../types';
import { EquipmentIcon, getPaletteIconDimensions } from '../canvas/EquipmentIcons';
const categoryOrder = [
    EquipmentCategory.Streams,
    EquipmentCategory.Mixing,
    EquipmentCategory.HeatTransfer,
    EquipmentCategory.Separation,
    EquipmentCategory.PressureChange,
    EquipmentCategory.Reaction,
    EquipmentCategory.Logical,
    EquipmentCategory.Piping,
];
export default function EquipmentPalette() {
    const [expanded, setExpanded] = useState(Object.fromEntries(categoryOrder.map((c) => [c, true])));
    const toggle = (cat) => {
        setExpanded((prev) => ({ ...prev, [cat]: !prev[cat] }));
    };
    const onDragStart = (event, type) => {
        event.dataTransfer.setData('application/equipment-type', type);
        event.dataTransfer.effectAllowed = 'move';
    };
    return (_jsxs("div", { className: "w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col overflow-hidden", children: [_jsx("div", { className: "px-4 py-3 border-b border-gray-200 dark:border-gray-800", children: _jsx("h2", { className: "text-sm font-semibold text-gray-800 dark:text-gray-200 uppercase tracking-wider", children: "Equipment" }) }), _jsx("div", { className: "flex-1 overflow-y-auto custom-scrollbar", children: categoryOrder.map((category) => (_jsxs("div", { children: [_jsxs("button", { onClick: () => toggle(category), className: "w-full flex items-center gap-2 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 hover:bg-gray-100/50 dark:hover:bg-gray-800/50 transition-colors", children: [expanded[category] ? (_jsx(ChevronDown, { size: 14 })) : (_jsx(ChevronRight, { size: 14 })), _jsx("span", { className: "text-gray-500 dark:text-gray-400", children: category })] }), expanded[category] && (_jsx("div", { className: "pb-1", children: equipmentByCategory[category].map((eq) => {
                                const iconDims = getPaletteIconDimensions(eq.type);
                                return (_jsxs("div", { draggable: true, onDragStart: (e) => onDragStart(e, eq.type), className: "flex items-center gap-3 mx-2 px-3 py-2 rounded-md cursor-grab active:cursor-grabbing hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group", children: [_jsx("div", { className: "flex items-center justify-center w-6 h-6 shrink-0", children: _jsx(EquipmentIcon, { type: eq.type, width: iconDims.width, height: iconDims.height }) }), _jsx("span", { className: "text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100", children: eq.label })] }, eq.type));
                            }) }))] }, category))) })] }));
}
