'use client';
import {
  ActionIcon,
  AppShell,
  Badge,
  Burger,
  Button,
  Group,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Title
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { IconLogout } from '@tabler/icons-react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { PropsWithChildren, useEffect } from 'react';
import { clearAdminToken } from '@/lib/admin-auth';
import { ApiError, fetchAdminMe, fetchHealth, logoutAdmin } from '@/lib/api-client';

const links = [{ label: 'API Keys', href: '/' }];

export function AppLayout({ children }: PropsWithChildren) {
  const [opened, { toggle }] = useDisclosure();
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isLoginPage = pathname === '/login';

  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: true,
    retryDelay: 1000,
    refetchOnWindowFocus: false,
    staleTime: 5_000
  });
  const healthReady = health.data?.status === 'ok';
  const adminMe = useQuery({
    queryKey: ['admin-me'],
    queryFn: fetchAdminMe,
    enabled: healthReady,
    retry: false
  });

  const isAuthenticated = Boolean(adminMe.data?.username);

  useEffect(() => {
    if (!healthReady) return;
    if (adminMe.isError) {
      const status = adminMe.error instanceof ApiError ? adminMe.error.status : undefined;
      if (status === 401 && !isLoginPage) {
        router.replace('/login');
      }
    }
  }, [adminMe.error, adminMe.isError, healthReady, isLoginPage, router]);

  useEffect(() => {
    if (healthReady && isLoginPage && isAuthenticated) {
      router.replace('/');
    }
  }, [healthReady, isAuthenticated, isLoginPage, router]);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={
        isAuthenticated
          ? { width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }
          : undefined
      }
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            {isAuthenticated && (
              <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            )}
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
              <Badge color={isAuthenticated ? 'green' : 'gray'} variant="light">
                {isAuthenticated ? 'Authenticated' : 'Signed out'}
              </Badge>
              {isAuthenticated && (
                <ActionIcon
                  variant="default"
                  aria-label="Sign out"
                  onClick={async () => {
                    try {
                      await logoutAdmin();
                    } catch (error) {
                      notifications.show({
                        title: 'Sign out failed',
                        message: error instanceof Error ? error.message : 'Unable to sign out.',
                        color: 'red'
                      });
                    } finally {
                      clearAdminToken();
                      queryClient.clear();
                      router.replace('/login');
                    }
                  }}
                >
                  <IconLogout size={18} />
                </ActionIcon>
              )}
            </Group>
            {adminMe.isError && !isLoginPage && (
              <Text size="xs" c="red">
                {adminMe.error instanceof Error ? adminMe.error.message : 'Admin session required'}
              </Text>
            )}
          </Stack>
        </Group>
      </AppShell.Header>
      {isAuthenticated && (
        <AppShell.Navbar p="md">
          <AppShell.Section grow component={ScrollArea}>
            <Stack gap="xs">
              {links.map((link) => (
                <NavLink component={Link} key={link.href} href={link.href as any} label={link.label} active={pathname === link.href} />
              ))}
            </Stack>
          </AppShell.Section>
        </AppShell.Navbar>
      )}
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
