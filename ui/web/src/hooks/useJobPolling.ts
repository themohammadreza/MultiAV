import { useQuery } from '@tanstack/react-query';
import { fetchJobResult, isTerminal } from '@/lib/api-client';
import { ResultSummary } from '@/lib/api-types';
import { loadConfig } from '@/lib/config';
import { validateJobId } from '@/lib/validators';
import { useEffect, useMemo, useState } from 'react';

const config = loadConfig();

function shouldContinue(status?: string | null): boolean {
  if (!status) return true;
  if (isTerminal(status)) return false;
  return true;
}

export function useJobPolling(jobId?: string) {
  const [validationError, setValidationError] = useState<Error | null>(null);
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

  const query = useQuery<ResultSummary, Error>({
    queryKey: ['job', parsedId],
    queryFn: () => fetchJobResult(parsedId!),
    enabled: Boolean(parsedId),
    refetchInterval: (data) => {
      if (!data) return config.pollIntervalMs;
      return shouldContinue(data.status) ? config.pollIntervalMs : false;
    },
    retry(failureCount, error) {
      if (error.message.includes('UUID')) return false;
      return failureCount < 3;
    },
    staleTime: 1000
  });

  useEffect(() => {
    if (!parsedId) return;
    const timer = setTimeout(() => {
      if (query.isFetching || query.isLoading) return;
      query.refetch();
    }, config.pollTimeoutMs);
    return () => clearTimeout(timer);
  }, [parsedId, query]);

  return { ...query, validationError };
}
