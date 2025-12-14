'use client';

import { Alert, Button, Stack, Text } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useEffect } from 'react';

export default function ErrorBoundary({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error('Runtime error', { message: error.message });
  }, [error]);

  return (
    <Stack>
      <Alert icon={<IconAlertTriangle size={16} />} color="red" title="Something went wrong">
        <Text fw={500}>{error.message}</Text>
        <Text size="sm" c="dimmed">
          Verify API base URL and configuration, then retry.
        </Text>
      </Alert>
      <Button onClick={reset} variant="light">
        Retry
      </Button>
    </Stack>
  );
}
