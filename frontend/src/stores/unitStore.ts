import { create } from 'zustand';
import { type UnitSystemName, getUnitSystem, type UnitSystem } from '../lib/unit-systems';

interface UnitState {
  unitSystemName: UnitSystemName;
  unitSystem: UnitSystem;
  setUnitSystem: (name: UnitSystemName) => void;
}

export const useUnitStore = create<UnitState>((set) => {
  const saved = (localStorage.getItem('prosim-unit-system') as UnitSystemName) || 'SI';
  return {
    unitSystemName: saved,
    unitSystem: getUnitSystem(saved),
    setUnitSystem: (name: UnitSystemName) => {
      localStorage.setItem('prosim-unit-system', name);
      set({ unitSystemName: name, unitSystem: getUnitSystem(name) });
    },
  };
});
