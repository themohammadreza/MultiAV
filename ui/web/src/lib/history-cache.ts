interface HistoryEntry {
  jobId: string;
  fileName: string;
  mimeType: string;
  size: number;
  startedAt?: string | null;
  completedAt?: string | null;
  verdict?: string | null;
  fileData?: string;
}

const KEY = 'multiav-upload-history';
const MAX_ENTRIES = 20;

function readStore(): HistoryEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function writeStore(entries: HistoryEntry[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // ignore storage issues
  }
}

export function addToHistory(entry: HistoryEntry, persistBytes: boolean) {
  const current = readStore();
  const sanitized: HistoryEntry = {
    ...entry,
    fileData: persistBytes ? entry.fileData : undefined
  };
  const next = [sanitized, ...current.filter((item) => item.jobId !== entry.jobId)];
  writeStore(next);
}

export function getHistory(): HistoryEntry[] {
  return readStore();
}
