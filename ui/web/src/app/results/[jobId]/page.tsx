'use client';

import { useParams } from 'next/navigation';
import { useJobPolling } from '@/hooks/useJobPolling';
import { Alert, Card, Loader, Stack, Text, Title } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { ResultSummaryCard } from '@/components/ResultSummary';

export default function ResultPage() {
  const params = useParams<{ jobId: string }>();
  const query = useJobPolling(params?.jobId);

  return (
    <Stack gap="md">
      <Title order={2}>Results</Title>
      {query.error && (
        <Alert color="red" icon={<IconAlertCircle size={16} />}>
          {query.error.message}
        </Alert>
      )}
      {query.isLoading || query.isFetching ? (
        <Card withBorder>
          <Stack align="center" gap="sm">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">
              Loading results…
            </Text>
          </Stack>
        </Card>
      ) : query.data ? (
        <ResultSummaryCard summary={query.data} />
      ) : (
        <Text size="sm" c="dimmed">
          No results yet.
        </Text>
      )}
    </Stack>
  );
}
