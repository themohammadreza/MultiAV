'use client';

import { Autocomplete, Button, Card, Group, Loader, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useJobPolling } from '@/hooks/useJobPolling';
import { notifications } from '@mantine/notifications';
import { useRouter } from 'next/navigation';
import { IconArrowRight } from '@tabler/icons-react';
import { validateJobId } from '@/lib/validators';
import { ActiveEnginesCard } from '@/components/ActiveEnginesCard';
import { fetchRecentJobs } from '@/lib/api-client';

export default function StatusPage() {
  const [jobId, setJobId] = useState('');
  const router = useRouter();
  const query = useJobPolling(jobId);
  const recentJobs = useQuery({ queryKey: ['recent-jobs'], queryFn: fetchRecentJobs, staleTime: 30_000 });

  const recentJobIds = useMemo(() => {
    const items = Array.isArray(recentJobs.data?.items) ? recentJobs.data?.items : [];
    const ids = items.map((item) => item.job_id).filter(Boolean);
    return Array.from(new Set(ids));
  }, [recentJobs.data]);

  const handleInspect = (nextJobId?: string) => {
    try {
      const candidate = (nextJobId ?? jobId).trim();
      setJobId(candidate);
      const valid = validateJobId(candidate);
      router.push(`/results/${valid}`);
    } catch (error) {
      notifications.show({ title: 'Invalid Job ID', message: (error as Error).message, color: 'red' });
    }
  };

  return (
    <Stack gap="md">
      <Title order={2}>Live status</Title>
      <Card withBorder>
        <Stack>
          <Group align="flex-end">
            <Autocomplete
              label="Job ID"
              placeholder="Search or enter a job UUID"
              value={jobId}
              onChange={setJobId}
              onOptionSubmit={handleInspect}
              data={recentJobIds || []}
              limit={20}
              comboboxProps={{ withinPortal: false }}
              rightSection={recentJobs.isFetching ? <Loader size="xs" /> : undefined}
              w="100%"
            />
            <Button onClick={handleInspect} leftSection={<IconArrowRight size={16} />}>
              Open results
            </Button>
          </Group>
          {query.validationError && <Text c="red">{query.validationError.message}</Text>}
          {query.error && <Text c="red">{query.error.message}</Text>}
          {query.data && (
            <Card withBorder>
              <Stack gap="xs">
                <Group justify="space-between">
                  <Text fw={600}>Job {query.data.job_id}</Text>
                  <Text>{query.data.status}</Text>
                </Group>
                <Text size="sm" c="dimmed">
                  Started {query.data.started_at ? new Date(query.data.started_at).toLocaleString() : 'pending'}
                </Text>
                {query.data.completed_at && (
                  <Text size="sm">Completed {new Date(query.data.completed_at).toLocaleString()}</Text>
                )}
                {query.data.verdict && <Text size="sm">Verdict: {query.data.verdict}</Text>}
              </Stack>
            </Card>
          )}
        </Stack>
      </Card>
      <ActiveEnginesCard />
    </Stack>
  );
}
