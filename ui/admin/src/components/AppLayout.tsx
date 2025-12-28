'use client';
import {
  ActionIcon,
  AppShell,
  Badge,
  Burger,
  Button,
  Group,
  Modal,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Title
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { IconKey } from '@tabler/icons-react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { PropsWithChildren, useEffect, useState } from 'react';
import { clearApiKey, getApiKey, setApiKey } from '@/lib/api-key';
import { fetchApiKeyStatus, fetchHealth } from '@/lib/api-client';

const links = [{ label: 'API Keys', href: '/' }];

export function AppLayout({ children }: PropsWithChildren) {
  const [opened, { toggle }] = useDisclosure();
  const [apiKeyModalOpen, apiKeyModal] = useDisclosure(false);
  const [storedApiKey, setStoredApiKey] = useState<string | null>(null);
  const [draftApiKey, setDraftApiKey] = useState('');
  const pathname = usePathname();
  const queryClient = useQueryClient();

  useEffect(() => {
    setStoredApiKey(getApiKey());
  }, []);

  const hasApiKey = Boolean(storedApiKey);
  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: true,
    retryDelay: 1000,
    refetchOnWindowFocus: false,
    staleTime: 5_000
  });
  const healthReady = health.data?.status === 'ok';
  const apiKeyStatus = useQuery({
    queryKey: ['api-key-info'],
    queryFn: fetchApiKeyStatus,
    enabled: hasApiKey && healthReady,
    refetchOnWindowFocus: false,
    staleTime: 30_000
  });

  const quotaParts =
    hasApiKey && apiKeyStatus.data && !apiKeyStatus.data.bypassed
      ? [
          apiKeyStatus.data.name?.trim(),
          `${apiKeyStatus.data.days_remaining ?? 0} day(s) left`,
          apiKeyStatus.data.requests_remaining_today == null
            ? 'unlimited requests today'
            : `${apiKeyStatus.data.requests_remaining_today} request(s) left today`
        ].filter((part): part is string => Boolean(part))
      : null;

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <Modal opened={apiKeyModalOpen} onClose={apiKeyModal.close} title="API key" centered keepMounted={false} withinPortal>
        <Stack>
          <TextInput
            label="X-API-Key"
            placeholder="Paste your admin API key"
            type="password"
            value={draftApiKey}
            onChange={(event) => setDraftApiKey(event.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                clearApiKey();
                setStoredApiKey(null);
                setDraftApiKey('');
                queryClient.invalidateQueries();
                notifications.show({ title: 'API key cleared', message: 'Requests will be unauthenticated.', color: 'gray' });
                apiKeyModal.close();
              }}
            >
              Clear
            </Button>
            <Button
              onClick={() => {
                const trimmed = draftApiKey.trim();
                if (!trimmed) {
                  notifications.show({ title: 'API key missing', message: 'Paste a key or click Clear.', color: 'red' });
                  return;
                }
                setApiKey(trimmed);
                setStoredApiKey(trimmed);
                queryClient.invalidateQueries();
                notifications.show({ title: 'API key saved', message: 'Requests will include X-API-Key.', color: 'green' });
                apiKeyModal.close();
              }}
            >
              Save
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            The key is stored in your browser local storage and sent as the <code>X-API-Key</code> header.
          </Text>
        </Stack>
      </Modal>
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            <Group gap="xs" align="center">
              <Image
                src="/greenweb.svg"
                alt="GreenWeb logo"
                width={28}
                height={28}
                priority
                unoptimized
                style={{ display: 'block' }}
              />
              <Title order={3}>MultiAV Admin</Title>
            </Group>
          </Group>
          <Stack gap={2} align="flex-end">
            <Group gap="xs">
              <Badge color={hasApiKey ? 'green' : 'gray'} variant="light">
                {hasApiKey ? 'API key set' : 'API key missing'}
              </Badge>
              <ActionIcon
                variant="default"
                aria-label="Configure API key"
                onClick={() => {
                  setDraftApiKey(storedApiKey ?? '');
                  apiKeyModal.open();
                }}
              >
                <IconKey size={18} />
              </ActionIcon>
            </Group>
            {quotaParts && <Text size="xs" c="dimmed">{quotaParts.join(' • ')}</Text>}
            {hasApiKey && apiKeyStatus.isError && (
              <Text size="xs" c="red">
                {apiKeyStatus.error.message}
              </Text>
            )}
          </Stack>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="md">
        <AppShell.Section grow component={ScrollArea}>
          <Stack gap="xs">
            {links.map((link) => (
              <NavLink component={Link} key={link.href} href={link.href as any} label={link.label} active={pathname === link.href} />
            ))}
          </Stack>
        </AppShell.Section>
      </AppShell.Navbar>
      <AppShell.Main>
        {!healthReady ? (
          <Stack align="center" mt="md" gap="xs">
            <Text>Warming up the server… please wait.</Text>
            {health.isError && (
              <Text size="sm" c="red">
                {health.error instanceof Error ? health.error.message : 'Server is starting up'}
              </Text>
            )}
          </Stack>
        ) : (
          children
        )}
      </AppShell.Main>
    </AppShell>
  );
}
