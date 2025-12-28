export interface ApiKeyStatusResponse {
  bypassed?: boolean;
  name?: string;
  rate_limit_per_day?: number;
  requests_used_today?: number;
  requests_remaining_today?: number | null;
  resets_at?: string | null;
  expires_at?: string;
  days_remaining?: number;
}

export interface AdminApiKey {
  id: string;
  name: string;
  rate_limit_per_day: number;
  created_at: string;
  revoked_at?: string | null;
  last_used_at?: string | null;
  raw_key?: string | null;
}

export interface AdminKeyScanItem {
  job_id: string;
  status: string;
  verdict?: string | null;
  created_at: string;
}

export interface AdminKeyScansResponse {
  items: AdminKeyScanItem[];
  count: number;
  total: number;
}
