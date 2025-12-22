export interface AppConfig {
  apiBaseUrl: string;
  uploadSizeLimitMb: number;
  pollIntervalMs: number;
  pollTimeoutMs: number;
}

function parseNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function loadConfig(): AppConfig {
  const uploadLimit = process.env.NEXT_PUBLIC_UPLOAD_SIZE_LIMIT_MB || process.env.NEXT_PUBLIC_UPLOAD_LIMIT_MB;
  return {
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || '',
    uploadSizeLimitMb: parseNumber(uploadLimit, 50),
    pollIntervalMs: parseNumber(process.env.NEXT_PUBLIC_POLL_INTERVAL_MS, 2000),
    pollTimeoutMs: parseNumber(process.env.NEXT_PUBLIC_POLL_TIMEOUT_MS, 10000)
  };
}
