import { useQuery } from '@tanstack/react-query';
import { fetchJobResult } from '@/lib/api-client';
import { JobStatus, ResultSummary } from '@/lib/api-types';
import { loadConfig } from '@/lib/config';
import { validateJobId } from '@/lib/validators';
import { useEffect } from 'react';

const config = loadConfig();

function shouldContinue(status: JobStatus): boolean {
  return status === 'pending' || status === 'running';
}

export function useJobPolling(jobId?: string) {
  const parsedId = jobId ? validateJobId(jobId) : undefined;
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

  return query;
}
