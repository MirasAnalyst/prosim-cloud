import { create } from 'zustand';

interface Annotation {
  id: string;
  type: 'text' | 'arrow' | 'rect';
  position: { x: number; y: number };
  size: { width: number; height: number };
  content: string;
  style: { color: string; fontSize: number };
}

interface AnnotationState {
  annotations: Annotation[];
  addAnnotation: (type: 'text' | 'arrow' | 'rect', position: { x: number; y: number }) => void;
  updateAnnotation: (id: string, updates: Partial<Annotation>) => void;
  removeAnnotation: (id: string) => void;
}

export const useAnnotationStore = create<AnnotationState>((set) => ({
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
