'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchRecentJobs } from '@/lib/api-client';
import { getHistory } from '@/lib/history-cache';
import { Badge, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import Link from 'next/link';

export default function HistoryPage() {
  const { data } = useQuery({ queryKey: ['recent-jobs'], queryFn: fetchRecentJobs });
  const cachedHistory = getHistory();

  return (
    <Stack gap="md">
      <Title order={2}>History</Title>
      <Card withBorder>
        <Stack>
          <Group justify="space-between">
            <Text fw={600}>Recent jobs (server)</Text>
            <Badge>{data?.count ?? 0}</Badge>
          </Group>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Job ID</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Verdict</Table.Th>
                <Table.Th>Severity</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {(data?.items ?? []).map((job) => (
                <Table.Tr key={job.job_id} component={Link} href={`/results/${job.job_id}`}>
                  <Table.Td>{job.job_id}</Table.Td>
                  <Table.Td>{job.status}</Table.Td>
                  <Table.Td>{job.verdict ?? 'pending'}</Table.Td>
                  <Table.Td>{job.severity ?? 'n/a'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Card>

      <Card withBorder>
        <Stack>
          <Group justify="space-between">
            <Text fw={600}>Cached uploads (client)</Text>
            <Badge>{cachedHistory.length}</Badge>
          </Group>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Job</Table.Th>
                <Table.Th>File</Table.Th>
                <Table.Th>Size</Table.Th>
                <Table.Th>Cached bytes</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {cachedHistory.map((entry) => (
                <Table.Tr key={entry.jobId} component={Link} href={`/results/${entry.jobId}`}>
                  <Table.Td>{entry.jobId}</Table.Td>
                  <Table.Td>{entry.fileName}</Table.Td>
                  <Table.Td>{(entry.size / 1024).toFixed(1)} KB</Table.Td>
                  <Table.Td>{entry.fileData ? 'yes' : 'no'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Card>
    </Stack>
  );
}
