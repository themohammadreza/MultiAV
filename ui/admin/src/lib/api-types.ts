export interface AdminAuthResponse {
  token: string;
  expires_at: string;
}

export interface AdminMeResponse {
  username: string;
  expires_at?: string | null;
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
