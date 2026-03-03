import { create } from 'zustand';
import { listVersions, createVersion, deleteVersion as apiDeleteVersion, restoreVersion as apiRestoreVersion, diffVersions, } from '../lib/api-client';
export const useVersionStore = create((set, get) => ({
    versions: [],
    loading: false,
    panelOpen: false,
    diffResult: null,
    togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
    loadVersions: async (projectId) => {
        set({ loading: true });
        try {
            const versions = await listVersions(projectId);
            set({ versions, loading: false });
        }
        catch {
            set({ loading: false });
        }
    },
    saveVersion: async (projectId, label) => {
        set({ loading: true });
        try {
            await createVersion(projectId, label);
            await get().loadVersions(projectId);
        }
        catch {
            set({ loading: false });
        }
    },
    removeVersion: async (projectId, versionId) => {
        try {
            await apiDeleteVersion(projectId, versionId);
            await get().loadVersions(projectId);
        }
        catch {
            // ignore
        }
    },
    restore: async (projectId, versionId) => {
        set({ loading: true });
        try {
            await apiRestoreVersion(projectId, versionId);
            set({ loading: false });
        }
        catch {
            set({ loading: false });
        }
    },
    computeDiff: async (projectId, v1, v2) => {
        try {
            const diff = await diffVersions(projectId, v1, v2);
            set({ diffResult: diff });
        }
        catch {
            set({ diffResult: null });
        }
    },
}));
