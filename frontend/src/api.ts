import { ChatResponse, AgentInfo, ToolInfo, HealthInfo } from './types';

const API_BASE = '/api/v1';

export async function sendChatMessage(
  message: string,
  token?: string,
  orgId?: string
): Promise<ChatResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;

  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message }),
  });

  if (!res.ok) {
    let errorDetail = 'Failed to connect to BugPilot server.';
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      /* fallback */
    }
    throw new Error(errorDetail);
  }

  return await res.json();
}

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return await res.json();
}

export async function fetchAgents(): Promise<{ count: number; agents: AgentInfo[]; data_source: string }> {
  const res = await fetch(`${API_BASE}/agents`);
  if (!res.ok) throw new Error('Failed to fetch agents');
  return await res.json();
}

export async function fetchTools(): Promise<{ count: number; tools: ToolInfo[]; data_source: string }> {
  const res = await fetch(`${API_BASE}/tools`);
  if (!res.ok) throw new Error('Failed to fetch tools');
  return await res.json();
}

export async function fetchDashboardMetrics(
  token?: string,
  orgId?: string,
  project?: string,
  component?: string
): Promise<any> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;

  const params = new URLSearchParams();
  if (project && project !== 'all') params.append('project', project);
  if (component && component !== 'all') params.append('component', component);

  const url = `${API_BASE}/metrics${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error('Failed to fetch dashboard metrics');
  return await res.json();
}

export async function fetchReadiness(): Promise<any> {
  const res = await fetch(`${API_BASE}/health/readiness`);
  if (!res.ok) throw new Error('Failed to fetch readiness status');
  return await res.json();
}

export async function executeMcpTool(toolName: string, token?: string, orgId?: string): Promise<any> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;

  const res = await fetch(`${API_BASE}/metrics`, { headers });
  if (!res.ok) throw new Error(`Execution of tool ${toolName} failed.`);
  const data = await res.json();
  return { tool: toolName, result: data, status: 'success' };
}





// Issue CRUD APIs
export async function fetchIssues(token?: string, orgId?: string): Promise<any[]> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;
  const res = await fetch(`${API_BASE}/issues`, { headers });
  if (!res.ok) throw new Error('Failed to fetch issues');
  return await res.json();
}

export async function createIssue(issueData: any, token?: string, orgId?: string): Promise<any> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;
  const res = await fetch(`${API_BASE}/issues`, {
    method: 'POST',
    headers,
    body: JSON.stringify(issueData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create issue' }));
    throw new Error(err.detail || 'Failed to create issue');
  }
  return await res.json();
}

export async function updateIssue(issueId: string, issueData: any, token?: string, orgId?: string): Promise<any> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;
  const res = await fetch(`${API_BASE}/issues/${issueId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(issueData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update issue' }));
    throw new Error(err.detail || 'Failed to update issue');
  }
  return await res.json();
}

export async function deleteIssue(issueId: string, token?: string, orgId?: string): Promise<any> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (orgId) headers['X-Organization-ID'] = orgId;
  const res = await fetch(`${API_BASE}/issues/${issueId}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to delete issue' }));
    throw new Error(err.detail || 'Failed to delete issue');
  }
  return await res.json();
}

// Authentication API functions
export async function loginUser(credentials: { email: string; password: string }): Promise<{ access_token: string; user: any }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Invalid email or password.' }));
    throw new Error(err.detail || 'Login failed.');
  }
  return await res.json();
}

export async function registerUser(userData: { email: string; password: string; full_name: string; org_id?: string }): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...userData, org_id: userData.org_id || 'org-acme' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Registration failed.' }));
    throw new Error(err.detail || 'Registration failed.');
  }
  return await res.json();
}

export async function fetchMe(token: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Session expired or invalid token.');
  return await res.json();
}
