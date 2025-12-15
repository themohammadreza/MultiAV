const STORAGE_KEY = 'multiav-api-key';

export function getApiKey(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const key = window.localStorage.getItem(STORAGE_KEY);
    return key && key.trim().length ? key.trim() : null;
  } catch {
    return null;
  }
}

export function setApiKey(value: string): void {
  if (typeof window === 'undefined') return;
  const trimmed = (value || '').trim();
  try {
    if (!trimmed) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, trimmed);
  } catch {
    // ignore storage issues
  }
}

export function clearApiKey(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore storage issues
  }
}

