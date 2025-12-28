const STORAGE_KEY = 'multiav-admin-token';

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const token = window.localStorage.getItem(STORAGE_KEY);
    return token && token.trim().length ? token.trim() : null;
  } catch {
    return null;
  }
}

export function setAdminToken(value: string): void {
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

export function clearAdminToken(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore storage issues
  }
}
