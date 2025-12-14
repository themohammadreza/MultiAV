'use client';

import { useParams } from 'next/navigation';
import { useJobPolling } from '@/hooks/useJobPolling';
import { Alert, Badge, Card, Group, ScrollArea, Stack, Table, Text, Title } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { isTerminal } from '@/lib/api-client';

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
      {query.data && (
        <Card withBorder>
          <Stack>
            <Group justify="space-between">
              <Text fw={600}>Job {query.data.job_id}</Text>
              <Badge color={isTerminal(query.data.status) ? 'green' : 'blue'}>{query.data.status}</Badge>
            </Group>
            <Text size="sm" c="dimmed">
              Submitted {new Date(query.data.submitted_at).toLocaleString()} • Cached: {query.data.cached ? 'yes' : 'no'}
            </Text>
            {query.data.details && (
              <ScrollArea h={120} p="xs" type="auto">
                <pre>{JSON.stringify(query.data.details, null, 2)}</pre>
              </ScrollArea>
            )}
            <Stack gap="xs">
              <Text fw={600}>Engines</Text>
              <ScrollArea>
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Engine</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Signature</Table.Th>
                      <Table.Th>Message</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {query.data.engines.map((engine) => (
                      <Table.Tr key={engine.engine}>
                        <Table.Td>{engine.engine}</Table.Td>
                        <Table.Td>{engine.status}</Table.Td>
                        <Table.Td>{engine.signature ?? 'n/a'}</Table.Td>
                        <Table.Td>{engine.message ?? '—'}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            </Stack>
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
