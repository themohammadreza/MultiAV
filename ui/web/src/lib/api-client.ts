import { ActiveEnginesResponse, RecentJobsResponse, ResultSummary, ScanResponse, JobStatus, ApiKeyStatusResponse } from './api-types';
import { loadConfig } from './config';
import { getApiKey } from './api-key';

const config = loadConfig();
const TERMINAL_STATUSES: Array<JobStatus | string> = ['done', 'done_with_errors', 'error'];
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

export function isTerminal(status?: string | null): boolean {
  if (!status) return false;
  return TERMINAL_STATUSES.includes(status.toLowerCase());
}

function authHeaders(): HeadersInit | undefined {
  const apiKey = getApiKey();
  if (!apiKey) return undefined;
  return { 'X-API-Key': apiKey };
}

export async function submitScan(file: File): Promise<ScanResponse> {
  const form = new FormData();
  form.append('file', file);

  const response = await fetch(`${apiBase}/api/v1/scan/`, {
    method: 'POST',
    body: form,
    headers: authHeaders()
  });

  return handleResponse<ScanResponse>(response);
}

export async function fetchJobResult(jobId: string): Promise<ResultSummary> {
  const response = await fetch(`${apiBase}/api/v1/results/${jobId}/`, { headers: authHeaders() });
  return handleResponse<ResultSummary>(response);
}

export async function fetchRecentJobs(): Promise<RecentJobsResponse> {
  const response = await fetch(`${apiBase}/api/v1/ui/jobs/recent/`, { headers: authHeaders() });
  return handleResponse<RecentJobsResponse>(response);
}

export async function fetchActiveEngines(): Promise<ActiveEnginesResponse> {
  const response = await fetch(`${apiBase}/api/v1/ui/engines/active/`, { headers: authHeaders() });
  return handleResponse<ActiveEnginesResponse>(response);
}

export async function fetchApiKeyStatus(): Promise<ApiKeyStatusResponse> {
  const response = await fetch(`${apiBase}/api/v1/ui/api-key/`, { headers: authHeaders() });
  return handleResponse<ApiKeyStatusResponse>(response);
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${apiBase}/api/v1/health/`, { headers: authHeaders() });
  return handleResponse<{ status: string }>(response);
}
