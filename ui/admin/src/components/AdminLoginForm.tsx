'use client';

import { Button, Card, Group, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { setAdminToken } from '@/lib/admin-auth';
import { loginAdmin } from '@/lib/api-client';

export function AdminLoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const loginMutation = useMutation({
    mutationFn: () => loginAdmin({ username: username.trim(), password }),
    onSuccess: (data) => {
      if (data.token) {
        setAdminToken(data.token);
      }
      queryClient.invalidateQueries({ queryKey: ['admin-me'] });
      notifications.show({ title: 'Signed in', message: 'Welcome back.', color: 'green' });
      router.replace('/');
    },
    onError: (error) => {
      notifications.show({
        title: 'Sign in failed',
        message: error instanceof Error ? error.message : 'Check your credentials and try again.',
        color: 'red'
      });
    }
  });

  return (
    <Group justify="center" mt="xl">
      <Card withBorder padding="lg" radius="md" w="100%" maw={420}>
        <Stack>
          <Title order={3}>Admin sign in</Title>
          <Text size="sm" c="dimmed">
            Use your admin credentials to manage API keys.
          </Text>
          <TextInput
            label="Username"
            placeholder="admin"
            value={username}
            onChange={(event) => setUsername(event.currentTarget.value)}
          />
          <PasswordInput
            label="Password"
            placeholder="Your password"
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
          />
          <Button
            fullWidth
            loading={loginMutation.isPending}
            onClick={() => {
              if (!username.trim() || !password) {
                notifications.show({ title: 'Missing credentials', message: 'Enter a username and password.', color: 'red' });
                return;
              }
              loginMutation.mutate();
            }}
          >
            Sign in
          </Button>
        </Stack>
      </Card>
    </Group>
  );
}
