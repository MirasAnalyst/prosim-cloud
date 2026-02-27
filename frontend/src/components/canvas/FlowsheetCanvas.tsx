import { useCallback, useRef, type DragEvent } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import EquipmentNode from './EquipmentNode';
import StreamEdge from './StreamEdge';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { EquipmentType } from '../../types';

const nodeTypes = { equipment: EquipmentNode };
const edgeTypes = { stream: StreamEdge };

const defaultEdgeOptions = {
  type: 'stream',
  animated: true,
  markerEnd: { type: 'arrowclosed' as const, color: '#60a5fa' },
};

export default function FlowsheetCanvas() {
  const reactFlowRef = useRef<{ screenToFlowPosition: (pos: { x: number; y: number }) => { x: number; y: number } } | null>(null);
  const nodes = useFlowsheetStore((s) => s.nodes);
  const edges = useFlowsheetStore((s) => s.edges);
  const onNodesChange = useFlowsheetStore((s) => s.onNodesChange);
  const onEdgesChange = useFlowsheetStore((s) => s.onEdgesChange);
  const onConnect = useFlowsheetStore((s) => s.onConnect);
  const addNode = useFlowsheetStore((s) => s.addNode);
  const setSelectedNode = useFlowsheetStore((s) => s.setSelectedNode);

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();

      const typeStr = event.dataTransfer.getData('application/equipment-type');
      if (!typeStr || !(typeStr in EquipmentType)) return;

      const type = typeStr as EquipmentType;
      const rfInstance = reactFlowRef.current;
      if (!rfInstance) return;

      const position = rfInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      addNode(type, position);
    },
    [addNode]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, [setSelectedNode]);

  return (
    <div className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={(instance) => { reactFlowRef.current = instance; }}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        deleteKeyCode={['Backspace', 'Delete']}
        className="bg-gray-950"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#374151" gap={20} size={1} />
        <Controls
          className="!bg-gray-800 !border-gray-700 !rounded-lg !shadow-lg [&>button]:!bg-gray-800 [&>button]:!border-gray-600 [&>button]:!text-gray-300 [&>button:hover]:!bg-gray-700"
        />
        <MiniMap
          nodeColor="#4b5563"
          maskColor="rgba(0,0,0,0.6)"
          className="!bg-gray-900 !border-gray-700 !rounded-lg"
        />
      </ReactFlow>
    </div>
  );
}
