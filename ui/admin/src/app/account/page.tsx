'use client';

import { Card, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { fetchAdminProfile } from '@/lib/api-client';

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export default function MyAccountPage() {
  const profile = useQuery({
    queryKey: ['admin-profile'],
    queryFn: fetchAdminProfile
  });

  return (
    <Stack gap="lg">
      <Title order={2}>My account</Title>
      <Card withBorder>
        <Stack gap="xs">
          <Text fw={600}>{profile.data?.username ?? 'Loading…'}</Text>
          <Text size="sm" c="dimmed">
            Role: {profile.data?.is_superadmin ? 'Superadmin' : 'Admin'}
          </Text>
          <Text size="sm">Created: {formatDate(profile.data?.created_at)}</Text>
          <Text size="sm">Updated: {formatDate(profile.data?.updated_at)}</Text>
          <Text size="sm">Last login: {formatDate(profile.data?.last_login_at)}</Text>
        </Stack>
      </Card>
    </Stack>
  );
}
