import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react';
import { useSimulationStore } from '../../stores/simulationStore';
import { SimulationStatus } from '../../types';

export default function StreamEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  label,
}: EdgeProps) {
  const results = useSimulationStore((s) => s.results);
  const status = useSimulationStore((s) => s.status);

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8,
  });

  const streamResult =
    status === SimulationStatus.Completed && results?.streamResults
      ? results.streamResults[id]
      : null;

  const displayLabel = streamResult
    ? `${streamResult.temperature.toFixed(1)}°C | ${streamResult.pressure.toFixed(1)} kPa | ${streamResult.flowRate.toFixed(2)} kg/s`
    : label;

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: '#60a5fa',
          strokeWidth: 2,
        }}
        id={id}
      />
      {displayLabel && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="rounded bg-gray-800/90 px-2 py-0.5 text-[10px] text-gray-300 border border-gray-600"
          >
            {displayLabel}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
