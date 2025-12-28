import { AdminApiKey, AdminAuthResponse, AdminKeyScansResponse, AdminMeResponse } from './api-types';
import { loadConfig } from './config';
import { getAdminToken } from './admin-auth';

const config = loadConfig();
const apiBase = config.apiBaseUrl.replace(/\/+$/, '');

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    let message = body || 'Request failed';
    try {
      const parsed = JSON.parse(body);
      if (parsed && typeof parsed.detail === 'string') {
        message = parsed.detail;
      }
    } catch {
      // ignore invalid JSON
    }
    throw new ApiError(message, response.status);
  }

  const body = await response.text();
  if (!body) {
    return {} as T;
  }
  try {
    return JSON.parse(body) as T;
  } catch {
    throw new Error('Invalid JSON response');
  }
}

function authHeaders(): HeadersInit | undefined {
  const token = getAdminToken();
  if (!token) return undefined;
  return { Authorization: `Bearer ${token}` };
}

function withAuth(options: RequestInit = {}): RequestInit {
  const headers = { ...(options.headers || {}), ...(authHeaders() ?? {}) };
  return { ...options, headers, credentials: 'include' };
}

export async function loginAdmin(payload: { username: string; password: string }): Promise<AdminAuthResponse> {
  const response = await fetch(
    `${apiBase}/api/v1/admin/auth/login`,
    withAuth({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  );
  return handleResponse<AdminAuthResponse>(response);
}

export async function logoutAdmin(): Promise<{ ok: boolean }> {
  const response = await fetch(`${apiBase}/api/v1/admin/auth/logout`, withAuth({ method: 'POST' }));
  return handleResponse<{ ok: boolean }>(response);
}

export async function fetchAdminMe(): Promise<AdminMeResponse> {
  const response = await fetch(`${apiBase}/api/v1/admin/auth/me`, withAuth());
  return handleResponse<AdminMeResponse>(response);
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${apiBase}/api/v1/health`, withAuth());
  return handleResponse<{ status: string }>(response);
}

export async function listAdminKeys(): Promise<AdminApiKey[]> {
  const response = await fetch(`${apiBase}/api/v1/admin/keys/`, withAuth());
  return handleResponse<AdminApiKey[]>(response);
}

export async function createAdminKey(payload: { name: string; rate_limit_per_day?: number | null }): Promise<AdminApiKey> {
  const response = await fetch(
    `${apiBase}/api/v1/admin/keys/`,
    withAuth({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  );
  return handleResponse<AdminApiKey>(response);
}

export async function updateAdminKey(
  keyId: string,
  payload: { name?: string; rate_limit_per_day?: number | null; rotate?: boolean }
): Promise<AdminApiKey> {
  const response = await fetch(
    `${apiBase}/api/v1/admin/keys/${keyId}`,
    withAuth({
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  );
  return handleResponse<AdminApiKey>(response);
}

export async function revokeAdminKey(keyId: string): Promise<AdminApiKey> {
  const response = await fetch(`${apiBase}/api/v1/admin/keys/${keyId}/revoke`, withAuth({ method: 'POST' }));
  return handleResponse<AdminApiKey>(response);
}

export async function fetchAdminKeyScans(keyId: string, limit: number, offset: number): Promise<AdminKeyScansResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(
    `${apiBase}/api/v1/admin/keys/${keyId}/scans?${params.toString()}`,
    withAuth()
  );
  return handleResponse<AdminKeyScansResponse>(response);
}
