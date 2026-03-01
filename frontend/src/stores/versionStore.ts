import { create } from 'zustand';
import {
  listVersions,
  createVersion,
  deleteVersion as apiDeleteVersion,
  restoreVersion as apiRestoreVersion,
  diffVersions,
} from '../lib/api-client';

export interface VersionSummary {
  id: string;
  flowsheet_id: string;
  version_number: number;
  label: string | null;
  property_package: string | null;
  created_at: string;
}

export interface VersionDiff {
  added_nodes: Record<string, unknown>[];
  removed_nodes: Record<string, unknown>[];
  modified_nodes: Record<string, unknown>[];
  added_edges: Record<string, unknown>[];
  removed_edges: Record<string, unknown>[];
  modified_edges: Record<string, unknown>[];
}

interface VersionState {
  versions: VersionSummary[];
  loading: boolean;
  panelOpen: boolean;
  diffResult: VersionDiff | null;

  togglePanel: () => void;
  loadVersions: (projectId: string) => Promise<void>;
  saveVersion: (projectId: string, label?: string) => Promise<void>;
  removeVersion: (projectId: string, versionId: string) => Promise<void>;
  restore: (projectId: string, versionId: string) => Promise<void>;
  computeDiff: (projectId: string, v1: string, v2: string) => Promise<void>;
}

export const useVersionStore = create<VersionState>((set, get) => ({
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
    } catch {
      set({ loading: false });
    }
  },

  saveVersion: async (projectId, label) => {
    set({ loading: true });
    try {
      await createVersion(projectId, label);
      await get().loadVersions(projectId);
    } catch {
      set({ loading: false });
    }
  },

  removeVersion: async (projectId, versionId) => {
    try {
      await apiDeleteVersion(projectId, versionId);
      await get().loadVersions(projectId);
    } catch {
      // ignore
    }
  },

  restore: async (projectId, versionId) => {
    set({ loading: true });
    try {
      await apiRestoreVersion(projectId, versionId);
      set({ loading: false });
    } catch {
      set({ loading: false });
    }
  },

  computeDiff: async (projectId, v1, v2) => {
    try {
      const diff = await diffVersions(projectId, v1, v2);
      set({ diffResult: diff });
    } catch {
      set({ diffResult: null });
    }
  },
}));
