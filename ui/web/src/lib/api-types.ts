export type JobStatus = 'pending...' | 'queued' | 'running...' | 'done' | 'done_with_errors' | 'error';

export interface ScanResponse {
  job_id: string;
  status: JobStatus | string;
  cached: boolean;
  scanned_at?: string;
}

export interface EngineDetail {
  engine?: string;
  status?: string;
  detected?: boolean;
  signature?: string;
  severity_score?: number;
  confidence?: number;
  message?: string;
  scanned_at?: string | null;
  [key: string]: unknown;
}

export interface ResultSummary {
  job_id: string;
  status: JobStatus | string;
  verdict?: string | null;
  confidence?: number;
  severity?: string | null;
  severity_score?: number;
  engine_count?: number;
  started_at?: string | null;
  completed_at?: string | null;
  families?: string[] | null;
  primary_family?: string | null;
  categories?: string[] | null;
  signatures?: string[] | null;
  details?: Record<string, EngineDetail>;
}

export interface RecentJobItem {
  job_id: string;
  status: JobStatus | string;
  verdict?: string | null;
  severity?: string | null;
  sha256?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RecentJobsResponse {
  items: RecentJobItem[];
  count: number;
}

export interface ActiveEngine {
  engine: string;
  timeout?: number | null;
  weight?: number | null;
}

export interface ActiveEnginesResponse {
  engines: ActiveEngine[];
}
