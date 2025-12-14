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
              <Table.Th>Engine</Table.Th>
              <Table.Th>Timeout (s)</Table.Th>
              <Table.Th>Weight</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(data?.engines ?? []).map((engine) => (
              <Table.Tr key={engine.engine}>
                <Table.Td>{engine.engine}</Table.Td>
                <Table.Td>{engine.timeout ?? '—'}</Table.Td>
                <Table.Td>{engine.weight ?? '—'}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Card>
  );
}
