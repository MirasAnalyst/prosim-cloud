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
}) {
  return request<SimulationResultResponse>('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify(data),
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

// ── Agent Chat ──

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatResponseData {
  message: ChatMessage;
  usage: Record<string, number> | null;
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
