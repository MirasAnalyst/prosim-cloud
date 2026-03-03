import { supabase } from './supabase';
export const API_BASE = import.meta.env.VITE_API_URL ?? '';
async function getAuthHeaders() {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${session.access_token}`,
        };
    }
    return { 'Content-Type': 'application/json' };
}
async function request(path, options) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: { ...authHeaders, ...options?.headers },
    });
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${body}`);
    }
    if (res.status === 204)
        return undefined;
    return res.json();
}
export function listProjects() {
    return request('/api/projects');
}
export function getProject(id) {
    return request(`/api/projects/${id}`);
}
export function createProject(name, description) {
    return request('/api/projects', {
        method: 'POST',
        body: JSON.stringify({ name, description }),
    });
}
export function updateProject(id, data) {
    return request(`/api/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}
export function deleteProject(id) {
    return request(`/api/projects/${id}`, { method: 'DELETE' });
}
export function getFlowsheet(projectId) {
    return request(`/api/projects/${projectId}/flowsheet`);
}
export function saveFlowsheet(projectId, nodes, edges, simulationBasis) {
    const payload = { nodes, edges };
    if (simulationBasis) {
        payload.simulation_basis = simulationBasis;
    }
    return request(`/api/projects/${projectId}/flowsheet`, {
        method: 'PUT',
        body: JSON.stringify(payload),
    });
}
export function runSimulation(data, signal) {
    return request('/api/simulation/run', {
        method: 'POST',
        body: JSON.stringify(data),
        signal,
    });
}
export function getSimulationResults(simulationId) {
    return request(`/api/simulation/${simulationId}/results`);
}
export function searchCompounds(query) {
    return request(`/api/compounds/search?q=${encodeURIComponent(query)}`);
}
export function getChatHistory(projectId) {
    return request(`/api/projects/${projectId}/chat`);
}
export function saveChatMessages(projectId, messages) {
    return request(`/api/projects/${projectId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ messages }),
    });
}
export function clearChatHistory(projectId) {
    return request(`/api/projects/${projectId}/chat`, { method: 'DELETE' });
}
export function listVersions(projectId) {
    return request(`/api/projects/${projectId}/versions`);
}
export function createVersion(projectId, label) {
    return request(`/api/projects/${projectId}/versions`, {
        method: 'POST',
        body: JSON.stringify({ label: label ?? null }),
    });
}
export function deleteVersion(projectId, versionId) {
    return request(`/api/projects/${projectId}/versions/${versionId}`, { method: 'DELETE' });
}
export function restoreVersion(projectId, versionId) {
    return request(`/api/projects/${projectId}/versions/${versionId}/restore`, {
        method: 'POST',
    });
}
export function diffVersions(projectId, v1, v2) {
    return request(`/api/projects/${projectId}/versions/${v1}/diff/${v2}`);
}
// ── Export / Import ──
export async function exportFlowsheet(projectId, format) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/export?format=${format}`, {
        headers: authHeaders,
    });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    return res;
}
export async function importFlowsheet(projectId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const { data: { session } } = await supabase.auth.getSession();
    const headers = {};
    if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
    }
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/import`, {
        method: 'POST',
        headers,
        body: formData,
    });
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${body}`);
    }
    return res.json();
}
export function validateFlowsheet(nodes, edges) {
    return request('/api/flowsheet/validate', {
        method: 'POST',
        body: JSON.stringify({ nodes, edges }),
    });
}
// ── Results Export ──
export async function exportSimulationResults(results, format) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/api/simulation/export?format=${format}`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify(results),
    });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    return res;
}
// ── Backup / Restore ──
export async function downloadBackup(projectId) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/backup`, {
        headers: authHeaders,
    });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    return res;
}
export function restoreBackup(backupData) {
    return request('/api/projects/restore', {
        method: 'POST',
        body: JSON.stringify(backupData),
    });
}
export function runSensitivity(data) {
    return request('/api/simulation/sensitivity', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}
export function listCases(projectId) {
    return request(`/api/projects/${projectId}/cases`);
}
export function createCase(projectId, data) {
    return request(`/api/projects/${projectId}/cases`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}
export function deleteCase(projectId, caseId) {
    return request(`/api/projects/${projectId}/cases/${caseId}`, { method: 'DELETE' });
}
export function loadCase(projectId, caseId) {
    return request(`/api/projects/${projectId}/cases/${caseId}/load`, {
        method: 'POST',
    });
}
export function compareCases(projectId, caseIds) {
    return request(`/api/projects/${projectId}/cases/compare`, {
        method: 'POST',
        body: JSON.stringify({ case_ids: caseIds }),
    });
}
// ── Insights File Upload ──
export async function parseInsightsFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    const { data: { session } } = await supabase.auth.getSession();
    const headers = {};
    if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
    }
    const res = await fetch(`${API_BASE}/api/simulation/insights/parse`, {
        method: 'POST',
        headers,
        body: formData,
    });
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${body}`);
    }
    return res.json();
}
export async function runInsightsFromFile(file, economicParams, propertyPackage = 'PengRobinson') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('economic_params_json', JSON.stringify(economicParams));
    formData.append('property_package', propertyPackage);
    const { data: { session } } = await supabase.auth.getSession();
    const headers = {};
    if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
    }
    const res = await fetch(`${API_BASE}/api/simulation/insights/upload`, {
        method: 'POST',
        headers,
        body: formData,
    });
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${body}`);
    }
    return res.json();
}
export function agentChat(messages, flowsheetContext) {
    return request('/api/agent/chat', {
        method: 'POST',
        body: JSON.stringify({ messages, flowsheet_context: flowsheetContext }),
    });
}
export async function* agentChatStream(messages, flowsheetContext) {
    const authHeaders = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/api/agent/chat/stream`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ messages, flowsheet_context: flowsheetContext }),
    });
    if (!res.ok)
        throw new Error(`HTTP ${res.status}`);
    if (!res.body)
        throw new Error('No response body');
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done)
            break;
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
