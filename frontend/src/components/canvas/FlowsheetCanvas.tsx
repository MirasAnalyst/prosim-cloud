import { useCallback, useRef, type DragEvent } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ConnectionLineType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import EquipmentNode from './EquipmentNode';
import GroupNode from './GroupNode';
import StreamEdge from './StreamEdge';
import EnergyStreamEdge from './EnergyStreamEdge';
import AnnotationLayer from './AnnotationLayer';
import { useFlowsheetStore } from '../../stores/flowsheetStore';
import { EquipmentType } from '../../types';

const nodeTypes = { equipment: EquipmentNode, group: GroupNode };
const edgeTypes = { stream: StreamEdge, 'energy-stream': EnergyStreamEdge };

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
    <div className="flex-1 h-full relative">
      <AnnotationLayer />
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
        connectionLineType={ConnectionLineType.SmoothStep}
        snapToGrid
        snapGrid={[20, 20]}
        fitView
        deleteKeyCode={['Backspace', 'Delete']}
        className="bg-gray-50 dark:bg-gray-950"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#374151" gap={20} size={1} />
        <Controls
          className="!bg-gray-100 dark:!bg-gray-800 !border-gray-300 dark:!border-gray-700 !rounded-lg !shadow-lg [&>button]:!bg-gray-100 dark:[&>button]:!bg-gray-800 [&>button]:!border-gray-400 dark:[&>button]:!border-gray-600 [&>button]:!text-gray-700 dark:[&>button]:!text-gray-300 [&>button:hover]:!bg-gray-200 dark:[&>button:hover]:!bg-gray-700"
        />
        <MiniMap
          nodeColor="#4b5563"
          maskColor="rgba(0,0,0,0.6)"
          className="!bg-white dark:!bg-gray-900 !border-gray-300 dark:!border-gray-700 !rounded-lg"
        />
      </ReactFlow>
    </div>
  );
}
