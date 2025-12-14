'use client';

import { fetchActiveEngines } from '@/lib/api-client';
import { useQuery } from '@tanstack/react-query';
import { Badge, Card, Group, Stack, Table, Text } from '@mantine/core';

export function ActiveEnginesCard() {
  const { data } = useQuery({ queryKey: ['engines'], queryFn: fetchActiveEngines });

  return (
    <Card withBorder>
      <Stack>
        <Group justify="space-between">
          <Text fw={600}>Active engines</Text>
          <Badge>{data?.engines.length ?? 0}</Badge>
        </Group>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Version</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(data?.engines ?? []).map((engine) => (
              <Table.Tr key={engine.name}>
                <Table.Td>{engine.name}</Table.Td>
                <Table.Td>{engine.status}</Table.Td>
                <Table.Td>{engine.version ?? '—'}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Card>
  );
}
