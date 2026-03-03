import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAnnotationStore } from '../../stores/annotationStore';
export default function AnnotationLayer() {
    const annotations = useAnnotationStore(s => s.annotations);
    const updateAnnotation = useAnnotationStore(s => s.updateAnnotation);
    const removeAnnotation = useAnnotationStore(s => s.removeAnnotation);
    return (_jsx("div", { className: "absolute inset-0 pointer-events-none z-10", children: annotations.map(ann => (_jsxs("div", { className: "absolute pointer-events-auto cursor-move", style: { left: ann.position.x, top: ann.position.y }, draggable: true, onDragEnd: (e) => {
                updateAnnotation(ann.id, { position: { x: e.clientX, y: e.clientY } });
            }, children: [ann.type === 'text' && (_jsxs("div", { className: "relative group", children: [_jsx("input", { value: ann.content, onChange: (e) => updateAnnotation(ann.id, { content: e.target.value }), className: "bg-transparent border border-dashed border-gray-500 rounded px-1 text-gray-300 text-xs focus:outline-none focus:border-blue-400", style: { fontSize: ann.style.fontSize, color: ann.style.color, width: ann.size.width } }), _jsx("button", { onClick: () => removeAnnotation(ann.id), className: "absolute -top-2 -right-2 w-4 h-4 bg-red-600 text-white rounded-full text-xs hidden group-hover:block", children: "\u00D7" })] })), ann.type === 'rect' && (_jsxs("div", { className: "relative group", children: [_jsx("div", { className: "border border-dashed border-gray-500 rounded", style: { width: ann.size.width, height: ann.size.height } }), _jsx("button", { onClick: () => removeAnnotation(ann.id), className: "absolute -top-2 -right-2 w-4 h-4 bg-red-600 text-white rounded-full text-xs hidden group-hover:block", children: "\u00D7" })] }))] }, ann.id))) }));
}
