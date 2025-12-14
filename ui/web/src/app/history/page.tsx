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
                <Table.Tr key={job.job_id} style={{ cursor: 'pointer' }}>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {job.job_id}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {job.status}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {job.verdict ?? 'pending'}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {job.severity ?? 'n/a'}
                    </Link>
                  </Table.Td>
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
                <Table.Tr key={entry.jobId} style={{ cursor: 'pointer' }}>
                  <Table.Td>
                    <Link href={`/results/${entry.jobId}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {entry.jobId}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${entry.jobId}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {entry.fileName}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${entry.jobId}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {(entry.size / 1024).toFixed(1)} KB
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${entry.jobId}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {entry.fileData ? 'yes' : 'no'}
                    </Link>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      </Card>
    </Stack>
  );
}
