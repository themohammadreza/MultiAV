import { useQuery } from '@tanstack/react-query';
import { ApiError, fetchJobResult, isTerminal } from '@/lib/api-client';
import { ResultSummary } from '@/lib/api-types';
import { loadConfig } from '@/lib/config';
import { validateJobId } from '@/lib/validators';
import { useEffect, useMemo, useRef, useState } from 'react';

const config = loadConfig();

function shouldContinue(status?: string | null): boolean {
  if (!status) return true;
  if (isTerminal(status)) return false;
  return true;
}

export function useJobPolling(jobId?: string) {
  const [validationError, setValidationError] = useState<Error | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const parsedId = useMemo(() => {
    if (!jobId) return undefined;
    try {
      setValidationError(null);
      return validateJobId(jobId);
    } catch (error) {
      setValidationError(error as Error);
      return undefined;
    }
  }, [jobId]);

  useEffect(() => {
    startTimeRef.current = Date.now();
  }, [parsedId]);

  const query = useQuery<ResultSummary, Error>({
    queryKey: ['job', parsedId],
    queryFn: () => fetchJobResult(parsedId!),
    enabled: Boolean(parsedId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: (query) => {
      if (query.state.error) return false;
      if (!query.state.data) return config.pollIntervalMs;
      if (!shouldContinue(query.state.data.status)) return false;

      const elapsedMs = Date.now() - startTimeRef.current;
      if (elapsedMs < 15_000) return config.pollIntervalMs;
      if (elapsedMs < 60_000) return Math.min(config.pollIntervalMs * 2, 10_000);
      return Math.min(config.pollIntervalMs * 5, 20_000);
    },
    retry(failureCount, error) {
      if (error instanceof ApiError && error.status && error.status >= 400 && error.status < 500) {
        return false;
      }
      if (error.message.includes('UUID')) return false;
      return failureCount < 3;
    },
    staleTime: 1000
  });

  return { ...query, validationError };
}
