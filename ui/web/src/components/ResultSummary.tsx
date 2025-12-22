'use client';

import { Badge, Button, Card, Divider, Group, ScrollArea, Stack, Table, Text, Title } from '@mantine/core';
import type { ResultSummary as ResultSummaryData } from '@/lib/api-types';

interface Props {
  summary: ResultSummaryData;
}

function formatTitleCase(value?: string | number | null) {
  if (value === undefined || value === null || value === '') return '';

  const normalized = typeof value === 'number' ? value.toString() : value.replace(/[_-]+/g, ' ');

  return normalized
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ');
}

function formatList(items?: Array<string | null> | null) {
  if (!items || items.length === 0) return '—';
  return items.filter(Boolean).join(', ');
}

function formatSignatures(signatures?: ResultSummaryData['signatures']) {
  if (!signatures || signatures.length === 0) return '—';
  const rendered = signatures
    .map((sig) => {
      if (!sig) return null;
      if (typeof sig === 'string') return sig;
      if (typeof sig === 'object') {
        return (
          (sig as any).signature ||
          (sig as any).rule ||
          (sig as any).name ||
          (sig as any).detection_name ||
          JSON.stringify(sig)
        );
      }
      return String(sig);
    })
    .filter(Boolean);
  return rendered.length ? rendered.join(', ') : '—';
}

function toTableRows(details: ResultSummaryData['details'] = {}) {
  return Object.entries(details).map(([engine, payload]) => ({
    engine,
    status: payload?.status ?? 'unknown',
    verdict: (payload as any)?.verdict ?? (payload as any)?.detection_name ?? '',
    signature: (payload as any)?.signature ?? (payload as any)?.rule ?? '',
    severity: (payload as any)?.severity ?? (payload as any)?.severity_score ?? '',
    confidence: (payload as any)?.confidence ?? '',
    duration: (payload as any)?.duration_ms ?? (payload as any)?.duration ?? '',
    error: (payload as any)?.error ?? (payload as any)?.message ?? ''
  }));
}

export function ResultSummaryCard({ summary }: Props) {
  const rows = toTableRows(summary.details);
  const status = (summary.status || '').toLowerCase();
  const badgeColor =
    status === 'done' ? 'green' : status === 'done_with_errors' ? 'yellow' : status === 'error' ? 'red' : 'blue';
  const verdictLabel = formatTitleCase(summary.verdict || 'pending');
  const severityLabel = formatTitleCase(summary.severity || 'informational');

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Results</Title>
        <Badge color={badgeColor}>{summary.status}</Badge>
      </Group>

      <Card withBorder>
        <Stack gap="sm">
          <Group justify="space-between" align="flex-start">
            <Stack gap={4}>
              <Text fw={600}>Job</Text>
              <Text size="sm" c="dimmed">
                {summary.job_id}
              </Text>
            </Stack>
            <Stack gap={4} ta="right">
              <Text size="sm" c="dimmed">
                Started {summary.started_at ? new Date(summary.started_at).toLocaleString() : '—'}
              </Text>
              <Text size="sm" c="dimmed">
                Completed {summary.completed_at ? new Date(summary.completed_at).toLocaleString() : '—'}
              </Text>
            </Stack>
          </Group>

          <Group align="flex-start" grow>
            <Stack>
              <Text fw={600}>Verdict</Text>
              <Title order={3}>{verdictLabel}</Title>
            </Stack>
            <Stack>
              <Text fw={600}>Severity</Text>
              <Title order={3}>{severityLabel}</Title>
            </Stack>
            <Stack>
              <Text fw={600}>Confidence</Text>
              <Title order={3}>{summary.confidence ?? 0}</Title>
            </Stack>
          </Group>

          <Stack gap="sm">
            <Stack gap={2}>
              <Text fw={600}>Families:</Text>
              <Text>{formatList(summary.families)}</Text>
            </Stack>
            <Divider />
            <Stack gap={2}>
              <Text fw={600}>Primary family:</Text>
              <Text>{summary.primary_family || '—'}</Text>
            </Stack>
            <Divider />
            <Stack gap={2}>
              <Text fw={600}>Categories:</Text>
              <Text>{formatList(summary.categories)}</Text>
            </Stack>
            <Divider />
            <Stack gap={2}>
              <Text fw={600}>Signatures:</Text>
              <Text>{formatSignatures(summary.signatures)}</Text>
            </Stack>
            <Divider />
          </Stack>
        </Stack>
      </Card>

      {rows.length > 0 && (
        <Card withBorder>
          <Stack gap="sm">
            <Group justify="space-between">
              <Text fw={600}>Engine details</Text>
              <Badge color="gray">{rows.length}</Badge>
            </Group>
            <ScrollArea h={240} type="auto">
              <Table striped highlightOnHover withColumnBorders>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Engine</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Verdict</Table.Th>
                    <Table.Th>Signature</Table.Th>
                    <Table.Th>Severity</Table.Th>
                    <Table.Th>Confidence</Table.Th>
                    <Table.Th>Duration (ms)</Table.Th>
                    <Table.Th>Error</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((row) => (
                    <Table.Tr key={row.engine}>
                      <Table.Td>{row.engine}</Table.Td>
                      <Table.Td>{row.status}</Table.Td>
                      <Table.Td>{formatTitleCase(row.verdict) || '—'}</Table.Td>
                      <Table.Td>{row.signature || '—'}</Table.Td>
                      <Table.Td>{formatTitleCase(row.severity) || '—'}</Table.Td>
                      <Table.Td>{row.confidence ?? '—'}</Table.Td>
                      <Table.Td>{row.duration || '—'}</Table.Td>
                      <Table.Td>{row.error || '—'}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Stack>
        </Card>
      )}

      <Button
        variant="default"
        component="a"
        href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(summary, null, 2))}`}
        download={`multiav-summary-${summary.job_id}.json`}
      >
        Download raw JSON
      </Button>
    </Stack>
  );
}
