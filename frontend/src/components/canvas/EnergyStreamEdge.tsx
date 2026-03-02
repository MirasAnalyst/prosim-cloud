import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from '@xyflow/react';
import { useSimulationStore } from '../../stores/simulationStore';
import { SimulationStatus } from '../../types';

export default function EnergyStreamEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const results = useSimulationStore((s) => s.results);
  const status = useSimulationStore((s) => s.status);

  // Look up energy stream result
  let label = '';
  if (status === SimulationStatus.Completed && results?.streamResults) {
    const streamResult = (results.streamResults as Record<string, unknown>)?.[id] as Record<string, unknown> | undefined;
    if (streamResult?.type === 'energy' && streamResult.duty_kW != null) {
      label = `⚡ ${Number(streamResult.duty_kW).toFixed(1)} kW`;
    }
  }

  return (
    <>
      <BaseEdge
        path={edgePath}
        style={{
          ...style,
          stroke: '#F59E0B',
          strokeWidth: 2,
          strokeDasharray: '6 3',
        }}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="text-[9px] font-mono bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 px-1.5 py-0.5 rounded border border-orange-300 dark:border-orange-700"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
