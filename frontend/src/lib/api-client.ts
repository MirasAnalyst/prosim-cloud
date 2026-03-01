const API_BASE = import.meta.env.VITE_API_URL ?? '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Projects ──

export interface ProjectResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export function listProjects() {
  return request<ProjectResponse[]>('/api/projects');
}

export function getProject(id: string) {
  return request<ProjectResponse>(`/api/projects/${id}`);
}

export function createProject(name: string, description?: string) {
  return request<ProjectResponse>('/api/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  });
}

export function updateProject(id: string, data: { name?: string; description?: string }) {
  return request<ProjectResponse>(`/api/projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteProject(id: string) {
  return request<void>(`/api/projects/${id}`, { method: 'DELETE' });
}

// ── Flowsheets ──

export interface FlowsheetResponse {
  id: string;
  project_id: string;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  updated_at: string;
}

export function getFlowsheet(projectId: string) {
  return request<FlowsheetResponse>(`/api/projects/${projectId}/flowsheet`);
}

export function saveFlowsheet(
  projectId: string,
  nodes: Record<string, unknown>[],
  edges: Record<string, unknown>[]
) {
  return request<FlowsheetResponse>(`/api/projects/${projectId}/flowsheet`, {
    method: 'PUT',
    body: JSON.stringify({ nodes, edges }),
  });
}

// ── Simulation ──

export interface SimulationResultResponse {
  id: string;
  flowsheet_id: string | null;
  status: string;
  results: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
}

export function runSimulation(data: {
  flowsheet_id?: string;
  nodes?: Record<string, unknown>[];
  edges?: Record<string, unknown>[];
  property_package?: string;
  convergence_settings?: { max_iter: number; tolerance: number; damping: number };
}, signal?: AbortSignal) {
  return request<SimulationResultResponse>('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify(data),
    signal,
  });
}

export function getSimulationResults(simulationId: string) {
  return request<SimulationResultResponse>(`/api/simulation/${simulationId}/results`);
}

// ── Compounds ──

export interface CompoundResult {
  name: string;
  cas: string;
  formula: string;
}

export function searchCompounds(query: string) {
  return request<CompoundResult[]>(`/api/compounds/search?q=${encodeURIComponent(query)}`);
}

// ── Chat History ──

export interface ChatHistoryMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export function getChatHistory(projectId: string) {
  return request<{ messages: ChatHistoryMessage[] }>(`/api/projects/${projectId}/chat`);
}

export function saveChatMessages(projectId: string, messages: Array<{ role: string; content: string }>) {
  return request<{ status: string; count: number }>(`/api/projects/${projectId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ messages }),
  });
}

export function clearChatHistory(projectId: string) {
  return request<void>(`/api/projects/${projectId}/chat`, { method: 'DELETE' });
}

// ── Versions ──

export interface VersionResponse {
  id: string;
  flowsheet_id: string;
  version_number: number;
  label: string | null;
  property_package: string | null;
  created_at: string;
}

export interface VersionDiffResponse {
  added_nodes: Record<string, unknown>[];
  removed_nodes: Record<string, unknown>[];
  modified_nodes: Record<string, unknown>[];
  added_edges: Record<string, unknown>[];
  removed_edges: Record<string, unknown>[];
  modified_edges: Record<string, unknown>[];
}

export function listVersions(projectId: string) {
  return request<VersionResponse[]>(`/api/projects/${projectId}/versions`);
}

export function createVersion(projectId: string, label?: string) {
  return request<VersionResponse>(`/api/projects/${projectId}/versions`, {
    method: 'POST',
    body: JSON.stringify({ label: label ?? null }),
  });
}

export function deleteVersion(projectId: string, versionId: string) {
  return request<void>(`/api/projects/${projectId}/versions/${versionId}`, { method: 'DELETE' });
}

export function restoreVersion(projectId: string, versionId: string) {
  return request<VersionResponse>(`/api/projects/${projectId}/versions/${versionId}/restore`, {
    method: 'POST',
  });
}

export function diffVersions(projectId: string, v1: string, v2: string) {
  return request<VersionDiffResponse>(`/api/projects/${projectId}/versions/${v1}/diff/${v2}`);
}

// ── Export / Import ──

export async function exportFlowsheet(projectId: string, format: string): Promise<Response> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/export?format=${format}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

export async function importFlowsheet(projectId: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/import`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Validation ──

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export function validateFlowsheet(nodes: Record<string, unknown>[], edges: Record<string, unknown>[]) {
  return request<ValidationResult>('/api/flowsheet/validate', {
    method: 'POST',
    body: JSON.stringify({ nodes, edges }),
  });
}

// ── Results Export ──

export async function exportSimulationResults(results: Record<string, unknown>, format: string): Promise<Response> {
  const res = await fetch(`${API_BASE}/api/simulation/export?format=${format}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(results),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

// ── Backup / Restore ──

export async function downloadBackup(projectId: string): Promise<Response> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/backup`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

export function restoreBackup(backupData: Record<string, unknown>) {
  return request<ProjectResponse>('/api/projects/restore', {
    method: 'POST',
    body: JSON.stringify(backupData),
  });
}

// ── Agent Chat ──

export interface ChatMessage {
  role: string;
  content: string;
}

export interface FlowsheetEquipment {
  id: string;
  type: string;
  name: string;
  parameters?: Record<string, number | string | boolean>;
}

export interface FlowsheetConnection {
  source_id: string;
  source_port: string;
  target_id: string;
  target_port: string;
}

export interface FlowsheetActionData {
  equipment: FlowsheetEquipment[];
  connections: FlowsheetConnection[];
  mode?: 'replace' | 'add';
}

export interface ChatResponseData {
  message: ChatMessage;
  usage: Record<string, number> | null;
  flowsheet_action: FlowsheetActionData | null;
}

export function agentChat(messages: ChatMessage[], flowsheetContext?: Record<string, unknown>) {
  return request<ChatResponseData>('/api/agent/chat', {
    method: 'POST',
    body: JSON.stringify({ messages, flowsheet_context: flowsheetContext }),
  });
}

export async function* agentChatStream(
  messages: ChatMessage[],
  flowsheetContext?: Record<string, unknown>
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/api/agent/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, flowsheet_context: flowsheetContext }),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield line.slice(6);
      }
    }
  }
}
