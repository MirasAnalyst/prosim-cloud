import { create } from 'zustand';
import { getUnitSystem } from '../lib/unit-systems';
export const useUnitStore = create((set) => {
    const saved = localStorage.getItem('prosim-unit-system') || 'SI';
    return {
        unitSystemName: saved,
        unitSystem: getUnitSystem(saved),
        setUnitSystem: (name) => {
            localStorage.setItem('prosim-unit-system', name);
            set({ unitSystemName: name, unitSystem: getUnitSystem(name) });
        },
    };
});
