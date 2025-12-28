import { ApiKeyStatusResponse, AdminApiKey, AdminKeyScansResponse } from './api-types';
import { loadConfig } from './config';
import { getApiKey } from './api-key';

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
    if (response.status === 401 && !getApiKey()) {
      message = message ? `${message} (set X-API-Key in the UI)` : 'Unauthorized (set X-API-Key in the UI)';
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
  const apiKey = getApiKey();
  if (!apiKey) return undefined;
  return { 'X-API-Key': apiKey };
}

export async function fetchApiKeyStatus(): Promise<ApiKeyStatusResponse> {
  const response = await fetch(`${apiBase}/api/v1/ui/api-key`, { headers: authHeaders() });
  return handleResponse<ApiKeyStatusResponse>(response);
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${apiBase}/api/v1/health`, { headers: authHeaders() });
  return handleResponse<{ status: string }>(response);
}

export async function listAdminKeys(): Promise<AdminApiKey[]> {
  const response = await fetch(`${apiBase}/api/v1/admin/keys/`, { headers: authHeaders() });
  return handleResponse<AdminApiKey[]>(response);
}

export async function createAdminKey(payload: { name: string; rate_limit_per_day?: number | null }): Promise<AdminApiKey> {
  const headers = authHeaders() ?? {};
  const response = await fetch(`${apiBase}/api/v1/admin/keys/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(payload)
  });
  return handleResponse<AdminApiKey>(response);
}

export async function updateAdminKey(
  keyId: string,
  payload: { name?: string; rate_limit_per_day?: number | null; rotate?: boolean }
): Promise<AdminApiKey> {
  const headers = authHeaders() ?? {};
  const response = await fetch(`${apiBase}/api/v1/admin/keys/${keyId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(payload)
  });
  return handleResponse<AdminApiKey>(response);
}

export async function revokeAdminKey(keyId: string): Promise<AdminApiKey> {
  const response = await fetch(`${apiBase}/api/v1/admin/keys/${keyId}/revoke`, {
    method: 'POST',
    headers: authHeaders()
  });
  return handleResponse<AdminApiKey>(response);
}

export async function fetchAdminKeyScans(keyId: string, limit: number, offset: number): Promise<AdminKeyScansResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(`${apiBase}/api/v1/admin/keys/${keyId}/scans?${params.toString()}`, { headers: authHeaders() });
  return handleResponse<AdminKeyScansResponse>(response);
}
