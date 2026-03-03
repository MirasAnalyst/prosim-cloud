import { create } from 'zustand';
export const useAnnotationStore = create((set) => ({
    annotations: [],
    addAnnotation: (type, position) => {
        set(state => ({
            annotations: [...state.annotations, {
                    id: crypto.randomUUID(),
                    type,
                    position,
                    size: { width: type === 'arrow' ? 100 : 150, height: type === 'arrow' ? 2 : 40 },
                    content: type === 'text' ? 'Note' : '',
                    style: { color: '#9ca3af', fontSize: 12 },
                }],
        }));
    },
    updateAnnotation: (id, updates) => {
        set(state => ({
            annotations: state.annotations.map(a => a.id === id ? { ...a, ...updates } : a),
        }));
    },
    removeAnnotation: (id) => {
        set(state => ({ annotations: state.annotations.filter(a => a.id !== id) }));
    },
}));
