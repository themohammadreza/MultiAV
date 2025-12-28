export interface AppConfig {
  apiBaseUrl: string;
}

export function loadConfig(): AppConfig {
  return {
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || ''
  };
}
