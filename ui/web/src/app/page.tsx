'use client';

import { ActionIcon, Badge, Button, Card, FileButton, Flex, Group, Paper, Stack, Switch, Text, Title } from '@mantine/core';
import { IconUpload, IconX } from '@tabler/icons-react';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { notifications } from '@mantine/notifications';
import { useMutation } from '@tanstack/react-query';
import { addToHistory } from '@/lib/history-cache';
import { submitScan } from '@/lib/api-client';
import { loadConfig } from '@/lib/config';
import { UploadFormValues, uploadFormSchema } from '@/lib/validators';
import Link from 'next/link';

const config = loadConfig();

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const form = useForm<UploadFormValues>({
    resolver: zodResolver(uploadFormSchema),
    defaultValues: { cacheUpload: true }
  });

  const mutation = useMutation({
    mutationFn: async (values: UploadFormValues) => {
      if (!values.file) throw new Error('File required');
      if (values.file.size > config.uploadSizeLimitMb * 1024 * 1024) {
        throw new Error(`File exceeds ${config.uploadSizeLimitMb}MB limit`);
      }
      return submitScan(values.file);
    },
    onSuccess: async (data, variables) => {
      notifications.show({ title: 'Upload started', message: `Job ${data.job_id} ${data.status}`, color: 'blue' });
      const shouldPersistBytes = variables.cacheUpload && config.featureHistory;
      let encoded: string | undefined;
      if (shouldPersistBytes && selectedFile) {
        const buffer = await selectedFile.arrayBuffer();
        encoded = btoa(String.fromCharCode(...new Uint8Array(buffer)));
      }
      if (config.featureHistory) {
        addToHistory(
          {
            jobId: data.job_id,
            fileName: selectedFile?.name ?? 'unknown',
            mimeType: selectedFile?.type ?? 'application/octet-stream',
            size: selectedFile?.size ?? 0,
            startedAt: data.scanned_at ?? new Date().toISOString(),
            verdict: isStatusTerminal(data.status) ? data.status : undefined,
            fileData: encoded
          },
          shouldPersistBytes
        );
      }
    },
    onError: (error) => {
      notifications.show({ title: 'Upload failed', message: error.message, color: 'red' });
    }
  });

  return (
    <Stack gap="lg">
      <Title order={2}>Upload file</Title>
      <Card shadow="sm" radius="md" withBorder>
        <Stack>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Max size {config.uploadSizeLimitMb}MB • Cached uploads allow re-scan without re-selecting the file.
            </Text>
            <Badge color="primary">API: {config.apiBaseUrl}</Badge>
          </Group>
          <Controller
            control={form.control}
            name="file"
            render={({ field, fieldState }) => (
              <Stack gap="xs">
                <FileButton
                  onChange={(file) => {
                    setSelectedFile(file);
                    field.onChange(file);
                  }}
                  accept="application/octet-stream,text/plain,application/zip"
                >
                  {(props) => (
                    <Button leftSection={<IconUpload size={16} />} variant="light" {...props} disabled={mutation.isPending}>
                      Choose file
                    </Button>
                  )}
                </FileButton>
                {selectedFile && (
                  <Paper withBorder p="xs" radius="md">
                    <Flex align="center" justify="space-between">
                      <Stack gap={0}>
                        <Text fw={600}>{selectedFile.name}</Text>
                        <Text size="xs" c="dimmed">
                          {(selectedFile.size / 1024).toFixed(1)} KB • {selectedFile.type || 'unknown type'}
                        </Text>
                      </Stack>
                      <ActionIcon
                        variant="subtle"
                        aria-label="Clear file"
                        onClick={() => {
                          setSelectedFile(null);
                          field.onChange(null);
                        }}
                      >
                        <IconX size={16} />
                      </ActionIcon>
                    </Flex>
                  </Paper>
                )}
                {fieldState.error && (
                  <Text size="sm" c="red">
                    {fieldState.error.message}
                  </Text>
                )}
              </Stack>
            )}
          />

          <Controller
            control={form.control}
            name="cacheUpload"
            render={({ field }) => (
              <Switch
                label="Cache upload for re-scan (stores file client-side)"
                {...field}
                disabled={mutation.isPending || !config.featureHistory}
                checked={field.value}
              />
            )}
          />

          <Button
            onClick={form.handleSubmit((values) => mutation.mutate(values))}
            loading={mutation.isPending}
            disabled={!selectedFile}
          >
            Submit
          </Button>
        </Stack>
      </Card>
      <Card withBorder>
        <Stack gap="sm">
          <Title order={4}>Quick access</Title>
          <Text size="sm">
            After starting a scan you can follow progress on the status page or jump to a specific result when a job ID is
            available.
          </Text>
          <Group>
            <Button component={Link} href="/status" variant="default">
              Status dashboard
            </Button>
            <Button component={Link} href="/history" variant="subtle">
              View history
            </Button>
          </Group>
        </Stack>
      </Card>
    </Stack>
  );
}

function isStatusTerminal(status?: string | null) {
  if (!status) return false;
  const normalized = status.toLowerCase();
  return normalized === 'done' || normalized === 'done_with_errors' || normalized === 'error';
}
