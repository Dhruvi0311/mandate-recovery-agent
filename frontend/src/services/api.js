const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const res = await fetch(url, config);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const errorMsg = data?.detail || data?.error || `HTTP ${res.status}: ${res.statusText}`;
      throw new Error(errorMsg);
    }
    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
      throw new Error(`Unable to connect to backend at ${API_BASE_URL}. Ensure the FastAPI server is running.`);
    }
    throw err;
  }
}

export const api = {
  getHealth: () => request('/health'),
  getMandates: () => request('/api/mandates'),
  getMandateDetail: (attemptId) => request(`/api/mandates/${attemptId}`),
  analyzeRecovery: (attemptId) => request(`/api/recovery/${attemptId}/analyze`, { method: 'POST' }),
  getAgentConversation: (attemptId) => request(`/api/agent/${attemptId}`),
  sendAgentMessage: (attemptId, message) =>
    request(`/api/agent/${attemptId}/message`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  getRecoveryStatus: (attemptId) => request(`/api/recovery/${attemptId}/status`),
  executeRecovery: (attemptId) => request(`/api/recovery/${attemptId}/execute`, { method: 'POST' }),
  getBatchReport: (forceRecompute = false) =>
    request(`/api/batch-report${forceRecompute ? '?force_recompute=true' : ''}`),
  getAuditLog: (attemptId = null) =>
    request(`/api/audit-log${attemptId ? `?attempt_id=${encodeURIComponent(attemptId)}` : ''}`),
  getAttemptAuditRecord: (attemptId) => request(`/api/audit-log/${attemptId}`),
  simulateRogueAgent: (attemptId) =>
    request(`/api/agent/${attemptId}/simulate-rogue`, { method: 'POST' }),
};

export default api;
