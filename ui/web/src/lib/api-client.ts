import { ActiveEnginesResponse, RecentJobsResponse, ResultSummary, ScanResponse, JobStatus } from './api-types';
import { loadConfig } from './config';

const config = loadConfig();
const TERMINAL_STATUSES: Array<JobStatus | string> = ['done', 'done_with_errors', 'error'];

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Request failed');
  }
  return (await response.json()) as T;
}

export function isTerminal(status?: string | null): boolean {
  if (!status) return false;
  return TERMINAL_STATUSES.includes(status.toLowerCase());
}

export async function submitScan(file: File): Promise<ScanResponse> {
  const form = new FormData();
  form.append('file', file);

  const response = await fetch(`${config.apiBaseUrl}/api/v1/scan/`, {
    method: 'POST',
    body: form
  });

  return handleResponse<ScanResponse>(response);
}

export async function fetchJobResult(jobId: string): Promise<ResultSummary> {
  const response = await fetch(`${config.apiBaseUrl}/api/v1/results/${jobId}`);
  return handleResponse<ResultSummary>(response);
}

export async function fetchRecentJobs(): Promise<RecentJobsResponse> {
  const response = await fetch(`${config.apiBaseUrl}/ui/jobs/recent`);
  return handleResponse<RecentJobsResponse>(response);
}

export async function fetchActiveEngines(): Promise<ActiveEnginesResponse> {
  const response = await fetch(`${config.apiBaseUrl}/ui/engines/active`);
  return handleResponse<ActiveEnginesResponse>(response);
}
