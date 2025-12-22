'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchRecentJobs } from '@/lib/api-client';
import { toTitleCase } from '@/lib/formatters';
import { Badge, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import Link from 'next/link';

export default function HistoryPage() {
  const { data } = useQuery({ queryKey: ['recent-jobs'], queryFn: fetchRecentJobs });

  return (
    <Stack gap="md">
      <Title order={2}>History</Title>

      <Card withBorder>
        <Stack gap="xs">
          <Group justify="space-between">
            <Text fw={600}>Recent jobs (server)</Text>
            <Badge>{data?.count ?? 0}</Badge>
          </Group>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Job ID</Table.Th>
                <Table.Th>File Name</Table.Th>
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
                      {job.filename || '—'}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {toTitleCase(job.status)}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {toTitleCase(job.verdict ?? 'pending')}
                    </Link>
                  </Table.Td>
                  <Table.Td>
                    <Link href={`/results/${job.job_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                      {toTitleCase(job.severity ?? 'n/a')}
                    </Link>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Text size="sm" c="dimmed">
            Click on any record to open the full scan report.
          </Text>
        </Stack>
      </Card>
    </Stack>
  );
}
