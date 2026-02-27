import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { equipmentLibrary } from '../../lib/equipment-library';
import { X } from 'lucide-react';

export default function PropertyInspector() {
  const selectedNodeId = useFlowsheetStore((s) => s.selectedNodeId);
  const nodes = useFlowsheetStore((s) => s.nodes);
  const updateNodeData = useFlowsheetStore((s) => s.updateNodeData);
  const removeNode = useFlowsheetStore((s) => s.removeNode);
  const setSelectedNode = useFlowsheetStore((s) => s.setSelectedNode);

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!node) return null;

  const def = equipmentLibrary[node.data.equipmentType];

  return (
    <div className="w-72 bg-gray-900 border-l border-gray-800 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-200">Properties</h2>
        <button
          onClick={() => setSelectedNode(null)}
          className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-200"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Name</label>
          <input
            type="text"
            value={node.data.name}
            onChange={(e) => updateNodeData(node.id, { name: e.target.value })}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">Type</label>
          <div className="text-sm text-gray-300 bg-gray-800 border border-gray-700 rounded px-3 py-1.5">
            {def.label}
          </div>
        </div>

        <div className="border-t border-gray-800 pt-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Parameters
          </h3>
          <div className="space-y-3">
            {Object.entries(def.parameters).map(([key, paramDef]) => (
              <div key={key}>
                <label className="flex items-center justify-between text-xs text-gray-400 mb-1">
                  <span>{paramDef.label}</span>
                  {paramDef.unit && (
                    <span className="text-gray-500">{paramDef.unit}</span>
                  )}
                </label>
                {paramDef.type === 'boolean' ? (
                  <button
                    onClick={() =>
                      updateNodeData(node.id, {
                        parameters: {
                          ...node.data.parameters,
                          [key]: !node.data.parameters[key],
                        },
                      })
                    }
                    className={`w-full text-left px-3 py-1.5 rounded text-sm border ${
                      node.data.parameters[key]
                        ? 'bg-blue-500/20 border-blue-500 text-blue-300'
                        : 'bg-gray-800 border-gray-700 text-gray-300'
                    }`}
                  >
                    {node.data.parameters[key] ? 'Enabled' : 'Disabled'}
                  </button>
                ) : paramDef.type === 'number' ? (
                  <input
                    type="number"
                    value={node.data.parameters[key] as number}
                    min={paramDef.min}
                    max={paramDef.max}
                    onChange={(e) =>
                      updateNodeData(node.id, {
                        parameters: {
                          ...node.data.parameters,
                          [key]: parseFloat(e.target.value) || 0,
                        },
                      })
                    }
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
                  />
                ) : (
                  <input
                    type="text"
                    value={node.data.parameters[key] as string}
                    onChange={(e) =>
                      updateNodeData(node.id, {
                        parameters: {
                          ...node.data.parameters,
                          [key]: e.target.value,
                        },
                      })
                    }
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-gray-800 pt-4">
          <button
            onClick={() => {
              removeNode(node.id);
              setSelectedNode(null);
            }}
            className="w-full px-3 py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded text-sm hover:bg-red-500/20 transition-colors"
          >
            Delete Equipment
          </button>
        </div>
      </div>
    </div>
  );
}
