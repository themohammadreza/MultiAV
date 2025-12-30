export interface AdminAuthResponse {
  token: string;
  expires_at: string;
}

export interface AdminMeResponse {
  id: string;
  username: string;
  is_superadmin: boolean;
  expires_at?: string | null;
}

export interface AdminApiKey {
  id: string;
  name: string;
  rate_limit_per_day: number;
  created_at: string;
  revoked_at?: string | null;
  last_used_at?: string | null;
  is_active: boolean;
  expires_at: string;
  days_remaining: number;
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

export interface AdminUser {
  id: string;
  username: string;
  is_superadmin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
}
