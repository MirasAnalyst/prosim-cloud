import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export default function GroupNode({ data }) {
    return (_jsx("div", { style: { width: data.width, height: data.collapsed ? 40 : data.height }, className: "border-2 border-dashed border-blue-400/30 rounded-lg bg-blue-500/5 relative", children: _jsxs("div", { className: "absolute top-0 left-0 right-0 h-8 flex items-center px-2 gap-2", children: [_jsx("span", { className: "text-xs font-semibold text-blue-400", children: data.label }), _jsx("button", { onClick: data.onToggle, className: "text-xs text-gray-400 hover:text-gray-200", children: data.collapsed ? '\u25B6' : '\u25BC' }), _jsx("button", { onClick: data.onRemove, className: "text-xs text-red-400 hover:text-red-300 ml-auto", children: "\u00D7" })] }) }));
}
