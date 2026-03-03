import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react';
import { useSimulationStore } from '../../stores/simulationStore';
import { useUnitStore } from '../../stores/unitStore';
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
  const us = useUnitStore((s) => s.unitSystem);

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
    ? `${us.fromSI.temperature(streamResult.temperature).toFixed(1)} ${us.units.temperature} | ${us.fromSI.pressure(streamResult.pressure).toFixed(1)} ${us.units.pressure} | ${us.fromSI.massFlow(streamResult.flowRate).toFixed(2)} ${us.units.massFlow}`
    : label;

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: streamResult?.vapor_fraction != null
            ? streamResult.vapor_fraction > 0.9
              ? '#EF4444'
              : streamResult.vapor_fraction < 0.1
                ? '#3B82F6'
                : '#F59E0B'
            : '#60a5fa',
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
