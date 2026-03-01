import { useAnnotationStore } from '../../stores/annotationStore';

export default function AnnotationLayer() {
  const annotations = useAnnotationStore(s => s.annotations);
  const updateAnnotation = useAnnotationStore(s => s.updateAnnotation);
  const removeAnnotation = useAnnotationStore(s => s.removeAnnotation);

  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      {annotations.map(ann => (
        <div
          key={ann.id}
          className="absolute pointer-events-auto cursor-move"
          style={{ left: ann.position.x, top: ann.position.y }}
          draggable
          onDragEnd={(e) => {
            updateAnnotation(ann.id, { position: { x: e.clientX, y: e.clientY } });
          }}
        >
          {ann.type === 'text' && (
            <div className="relative group">
              <input
                value={ann.content}
                onChange={(e) => updateAnnotation(ann.id, { content: e.target.value })}
                className="bg-transparent border border-dashed border-gray-500 rounded px-1 text-gray-300 text-xs focus:outline-none focus:border-blue-400"
                style={{ fontSize: ann.style.fontSize, color: ann.style.color, width: ann.size.width }}
              />
              <button
                onClick={() => removeAnnotation(ann.id)}
                className="absolute -top-2 -right-2 w-4 h-4 bg-red-600 text-white rounded-full text-xs hidden group-hover:block"
              >
                &times;
              </button>
            </div>
          )}
          {ann.type === 'rect' && (
            <div className="relative group">
              <div
                className="border border-dashed border-gray-500 rounded"
                style={{ width: ann.size.width, height: ann.size.height }}
              />
              <button
                onClick={() => removeAnnotation(ann.id)}
                className="absolute -top-2 -right-2 w-4 h-4 bg-red-600 text-white rounded-full text-xs hidden group-hover:block"
              >
                &times;
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
