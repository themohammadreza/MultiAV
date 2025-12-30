'use client';

import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  Loader,
  Modal,
  NumberInput,
  Pagination,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { IconCopy, IconKey, IconPencil, IconRefresh, IconTrash } from '@tabler/icons-react';
import { useEffect, useMemo, useState } from 'react';
import { AdminApiKey } from '@/lib/api-types';
import { createAdminKey, deleteAdminKey, fetchAdminKeyScans, listAdminKeys, updateAdminKey } from '@/lib/api-client';
import { toTitleCase } from '@/lib/formatters';

const SCANS_PAGE_SIZE = 10;

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatRemainingDays(daysRemaining: number, isActive: boolean): string {
  if (!isActive) return 'Inactive';
  if (daysRemaining <= 0) return 'Expired';
  if (daysRemaining === 1) return '1 day left';
  return `${daysRemaining} days left`;
}

export default function AdminKeysPage() {
  const queryClient = useQueryClient();
  const [createName, setCreateName] = useState('');
  const [createRateLimit, setCreateRateLimit] = useState<number | ''>(60);
  const [createTouched, setCreateTouched] = useState(false);
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null);
  const [scanPage, setScanPage] = useState(1);
  const [editingKey, setEditingKey] = useState<AdminApiKey | null>(null);
  const [editName, setEditName] = useState('');
  const [editRateLimit, setEditRateLimit] = useState<number | ''>('');
  const [rotateKey, setRotateKey] = useState<AdminApiKey | null>(null);
  const [deleteKey, setDeleteKey] = useState<AdminApiKey | null>(null);
  const [rawKey, setRawKey] = useState<{ name: string; rawKey: string } | null>(null);
  const [rawKeyCopied, setRawKeyCopied] = useState(false);
  const [editModalOpened, editModal] = useDisclosure(false);
  const [rawKeyModalOpened, rawKeyModal] = useDisclosure(false);
  const [rotateModalOpened, rotateModal] = useDisclosure(false);
  const [deleteModalOpened, deleteModal] = useDisclosure(false);

  const keysQuery = useQuery({
    queryKey: ['admin-keys'],
    queryFn: listAdminKeys
  });

  const keys = keysQuery.data ?? [];

  useEffect(() => {
    if (!selectedKeyId && keys.length > 0) {
      setSelectedKeyId(keys[0].id);
    }
  }, [keys, selectedKeyId]);

  useEffect(() => {
    if (selectedKeyId && !keys.some((key) => key.id === selectedKeyId)) {
      setSelectedKeyId(keys[0]?.id ?? null);
    }
  }, [keys, selectedKeyId]);

  const selectedKey = useMemo(
    () => keys.find((key) => key.id === selectedKeyId) ?? null,
    [keys, selectedKeyId]
  );

  useEffect(() => {
    setScanPage(1);
  }, [selectedKeyId]);

  const scansQuery = useQuery({
    queryKey: ['admin-key-scans', selectedKeyId, scanPage],
    queryFn: () => fetchAdminKeyScans(selectedKeyId as string, SCANS_PAGE_SIZE, (scanPage - 1) * SCANS_PAGE_SIZE),
    enabled: Boolean(selectedKeyId),
    staleTime: 10_000,
    placeholderData: (previous) => previous
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createAdminKey({
        name: createName.trim(),
        rate_limit_per_day: createRateLimit === '' ? null : createRateLimit
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-keys'] });
      setCreateName('');
      setCreateRateLimit(60);
      setCreateTouched(false);
      notifications.show({ title: 'API key created', message: `Key ${data.name} is ready.`, color: 'green' });
      if (data.raw_key) {
        setRawKey({ name: data.name, rawKey: data.raw_key });
        setRawKeyCopied(false);
        rawKeyModal.open();
      }
    },
    onError: (error) => {
      notifications.show({ title: 'Create failed', message: error.message, color: 'red' });
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({
      keyId,
      ...payload
    }: {
      keyId: string;
      name?: string;
      rate_limit_per_day?: number | null;
      rotate?: boolean;
      is_active?: boolean;
    }) => updateAdminKey(keyId, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-keys'] });
      notifications.show({ title: 'API key updated', message: `Updated ${data.name}.`, color: 'green' });
      if (data.raw_key) {
        setRawKey({ name: data.name, rawKey: data.raw_key });
        setRawKeyCopied(false);
        rawKeyModal.open();
      }
    },
    onError: (error) => {
      notifications.show({ title: 'Update failed', message: error.message, color: 'red' });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (keyId: string) => deleteAdminKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-keys'] });
      notifications.show({ title: 'API key deleted', message: 'The API key was removed.', color: 'orange' });
    },
    onError: (error) => {
      notifications.show({ title: 'Delete failed', message: error.message, color: 'red' });
    }
  });

  const totalScanPages = scansQuery.data ? Math.max(1, Math.ceil(scansQuery.data.total / SCANS_PAGE_SIZE)) : 1;

  return (
    <Stack gap="lg">
      <Title order={2}>Admin Keys</Title>

      <Modal opened={editModalOpened} onClose={editModal.close} title="Rename or update quota" centered>
        <Stack>
          <TextInput label="Key name" value={editName} onChange={(event) => setEditName(event.currentTarget.value)} />
          <NumberInput
            label="Rate limit per day"
            value={editRateLimit}
            min={0}
            max={100000}
            onChange={(value) => {
              if (value === '') {
                setEditRateLimit('');
                return;
              }
              if (typeof value === 'number') {
                setEditRateLimit(value);
                return;
              }
              const parsed = Number(value);
              setEditRateLimit(Number.isNaN(parsed) ? '' : parsed);
            }}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={editModal.close}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!editingKey) return;
                updateMutation.mutate({
                  keyId: editingKey.id,
                  name: editName.trim() || undefined,
                  rate_limit_per_day: editRateLimit === '' ? undefined : editRateLimit
                });
                editModal.close();
              }}
            >
              Save changes
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={rawKeyModalOpened}
        onClose={() => {
          rawKeyModal.close();
          setRawKeyCopied(false);
        }}
        title="Copy your API key"
        centered
      >
        <Stack>
          <Text size="sm" c="dimmed">
            This key is shown only once. Store it in a secure vault before closing this dialog.
          </Text>
          <Card withBorder>
            <Text fw={600}>{rawKey?.name}</Text>
            <Group mt="xs" align="flex-start" gap="xs">
              <Text style={{ wordBreak: 'break-all', flex: 1 }}>{rawKey?.rawKey}</Text>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconCopy size={14} />}
                onClick={async () => {
                  if (!rawKey?.rawKey) return;
                  await navigator.clipboard.writeText(rawKey.rawKey);
                  setRawKeyCopied(true);
                  notifications.show({
                    title: 'Copied',
                    message: 'API key copied to clipboard.',
                    color: 'green'
                  });
                }}
              >
                Copy
              </Button>
            </Group>
          </Card>
          {rawKeyCopied && (
            <Text size="sm" fw={600} style={{ backgroundColor: 'var(--mantine-color-green-1)', color: 'var(--mantine-color-green-8)', padding: '6px 10px', borderRadius: 6 }}>
              Copied
            </Text>
          )}
          <Button
            onClick={() => {
              rawKeyModal.close();
              setRawKey(null);
              setRawKeyCopied(false);
            }}
          >
            I have copied it
          </Button>
        </Stack>
      </Modal>

      <Modal opened={rotateModalOpened} onClose={rotateModal.close} title="Rotate API key?" centered>
        <Stack>
          <Text>
            Rotating the key will invalidate the current secret for <strong>{rotateKey?.name}</strong>.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={rotateModal.close}>
              Cancel
            </Button>
            <Button
              color="orange"
              onClick={() => {
                if (!rotateKey) return;
                updateMutation.mutate({ keyId: rotateKey.id, rotate: true });
                rotateModal.close();
              }}
            >
              Rotate key
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={deleteModalOpened} onClose={deleteModal.close} title="Delete API key?" centered>
        <Stack>
          <Text>
            This will permanently delete <strong>{deleteKey?.name}</strong>.
          </Text>
          <Text size="sm" c="red">
            This action cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={deleteModal.close}>
              Cancel
            </Button>
            <Button
              color="red"
              onClick={() => {
                if (!deleteKey) return;
                deleteMutation.mutate(deleteKey.id);
                deleteModal.close();
              }}
            >
              Delete key
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Card withBorder>
        <Stack gap="md">
          <Group justify="space-between">
            <Title order={4}>Create API key</Title>
            <Badge color="gray">Admin</Badge>
          </Group>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              setCreateTouched(true);
              if (!createName.trim()) {
                return;
              }
              createMutation.mutate();
            }}
          >
            <Stack>
              <Group align="end">
                <TextInput
                  label="Key name"
                  placeholder="Frontend service"
                  value={createName}
                  onChange={(event) => setCreateName(event.currentTarget.value)}
                  style={{ flex: 1 }}
                  error={createTouched && !createName.trim()}
                />
                <NumberInput
                  label="Rate limit per day"
                  value={createRateLimit}
                  min={0}
                  max={100000}
                  onChange={(value) => {
                    if (value === '') {
                      setCreateRateLimit('');
                      return;
                    }
                    if (typeof value === 'number') {
                      setCreateRateLimit(value);
                      return;
                    }
                    const parsed = Number(value);
                    setCreateRateLimit(Number.isNaN(parsed) ? '' : parsed);
                  }}
                  style={{ maxWidth: 200 }}
                />
                <Button leftSection={<IconKey size={16} />} loading={createMutation.isPending} type="submit">
                  Create
                </Button>
              </Group>
              {createTouched && !createName.trim() && (
                <Text size="xs" c="red">
                  * Enter a key name to create an API key.
                </Text>
              )}
            </Stack>
          </form>
        </Stack>
      </Card>

      <Card withBorder>
        <Stack gap="md">
          <Group justify="space-between">
            <Title order={4}>API keys</Title>
            <Badge>{keys.length}</Badge>
          </Group>
          {keysQuery.isLoading ? (
            <Group>
              <Loader size="sm" />
              <Text size="sm">Loading keys…</Text>
            </Group>
          ) : keysQuery.isError ? (
            <Text c="red">Failed to load keys: {keysQuery.error.message}</Text>
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Quota/day</Table.Th>
                  <Table.Th>Created at</Table.Th>
                  <Table.Th>Expired at</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Last used</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {keys.map((key) => (
                  <Table.Tr key={key.id} style={{ cursor: 'pointer' }} onClick={() => setSelectedKeyId(key.id)}>
                    <Table.Td>
                      <Group gap="xs">
                        <Text fw={600}>{key.name}</Text>
                        {selectedKeyId === key.id && <Badge size="sm">Selected</Badge>}
                      </Group>
                    </Table.Td>
                    <Table.Td>{key.rate_limit_per_day}</Table.Td>
                    <Table.Td>
                      {formatDate(key.created_at)}
                    </Table.Td>
                    <Table.Td>{formatRemainingDays(key.days_remaining, key.is_active)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Badge color={key.is_active ? 'green' : 'red'}>
                          {key.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        <Switch
                          size="sm"
                          checked={key.is_active}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => {
                            event.stopPropagation();
                            updateMutation.mutate({
                              keyId: key.id,
                              is_active: event.currentTarget.checked
                            });
                          }}
                          aria-label={key.is_active ? 'Deactivate API key' : 'Activate API key'}
                        />
                      </Group>
                    </Table.Td>
                    <Table.Td>{formatDate(key.last_used_at)}</Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Tooltip label="Rename or update quota">
                          <ActionIcon
                            variant="default"
                            onClick={(event) => {
                              event.stopPropagation();
                              setEditingKey(key);
                              setEditName(key.name);
                              setEditRateLimit(key.rate_limit_per_day);
                              editModal.open();
                            }}
                          >
                            <IconPencil size={16} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label="Rotate key">
                          <ActionIcon
                            variant="default"
                            onClick={(event) => {
                              event.stopPropagation();
                              setRotateKey(key);
                              rotateModal.open();
                            }}
                          >
                            <IconRefresh size={16} />
                          </ActionIcon>
                        </Tooltip>
                        <Tooltip label="Delete key">
                          <ActionIcon
                            variant="default"
                            color="red"
                            onClick={(event) => {
                              event.stopPropagation();
                              setDeleteKey(key);
                              deleteModal.open();
                            }}
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      </Card>

      <Card withBorder>
        <Stack gap="md">
          <Group justify="space-between">
            <Title order={4}>Recent scans</Title>
            {selectedKey ? <Badge>{selectedKey.name}</Badge> : <Badge color="gray">Select a key</Badge>}
          </Group>
          <Text size="sm" c="dimmed">
            Showing the latest scan activity for the selected key.
          </Text>
          <Divider />
          {!selectedKey ? (
            <Text size="sm" c="dimmed">
              Select an API key above to view its scans.
            </Text>
          ) : scansQuery.isLoading ? (
            <Group>
              <Loader size="sm" />
              <Text size="sm">Loading scans…</Text>
            </Group>
          ) : scansQuery.isError ? (
            <Text c="red">Failed to load scans: {scansQuery.error.message}</Text>
          ) : (
            <Stack gap="sm">
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Job ID</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Verdict</Table.Th>
                    <Table.Th>Queued at</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {(scansQuery.data?.items ?? []).map((scan) => (
                    <Table.Tr key={scan.job_id}>
                      <Table.Td>{scan.job_id}</Table.Td>
                      <Table.Td>{toTitleCase(scan.status)}</Table.Td>
                      <Table.Td>{scan.verdict ? toTitleCase(scan.verdict) : '—'}</Table.Td>
                      <Table.Td>{formatDate(scan.created_at)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
              {scansQuery.isFetching && (
                <Text size="xs" c="dimmed">
                  Refreshing…
                </Text>
              )}
              <Group justify="space-between">
                <Text size="xs" c="dimmed">
                  Showing {scansQuery.data?.count ?? 0} of {scansQuery.data?.total ?? 0} scans.
                </Text>
                <Pagination value={scanPage} onChange={setScanPage} total={totalScanPages} size="sm" />
              </Group>
            </Stack>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}
