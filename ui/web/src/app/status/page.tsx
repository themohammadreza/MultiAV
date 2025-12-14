'use client';

import { Button, Card, Group, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState } from 'react';
import { useJobPolling } from '@/hooks/useJobPolling';
import { notifications } from '@mantine/notifications';
import { useRouter } from 'next/navigation';
import { IconArrowRight } from '@tabler/icons-react';
import { validateJobId } from '@/lib/validators';
import { ActiveEnginesCard } from '@/components/ActiveEnginesCard';

export default function StatusPage() {
  const [jobId, setJobId] = useState('');
  const router = useRouter();
  const query = useJobPolling(jobId);

  const handleInspect = () => {
    try {
      const valid = validateJobId(jobId);
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
            <TextInput
              label="Job ID"
              placeholder="Enter job UUID"
              value={jobId}
              onChange={(event) => setJobId(event.currentTarget.value)}
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
