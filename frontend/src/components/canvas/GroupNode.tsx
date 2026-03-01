export default function GroupNode({ data }: { data: { label: string; collapsed: boolean; width: number; height: number; onRemove: () => void; onToggle: () => void } }) {
  return (
    <div
      style={{ width: data.width, height: data.collapsed ? 40 : data.height }}
      className="border-2 border-dashed border-blue-400/30 rounded-lg bg-blue-500/5 relative"
    >
      <div className="absolute top-0 left-0 right-0 h-8 flex items-center px-2 gap-2">
        <span className="text-xs font-semibold text-blue-400">{data.label}</span>
        <button onClick={data.onToggle} className="text-xs text-gray-400 hover:text-gray-200">
          {data.collapsed ? '\u25B6' : '\u25BC'}
        </button>
        <button onClick={data.onRemove} className="text-xs text-red-400 hover:text-red-300 ml-auto">&times;</button>
      </div>
    </div>
  );
}
