import { create } from 'zustand';
export const useThemeStore = create((set) => ({
    theme: localStorage.getItem('prosim-theme') || 'dark',
    toggleTheme: () => set((state) => {
        const next = state.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('prosim-theme', next);
        return { theme: next };
    }),
}));
