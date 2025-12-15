'use client';

import { ActionIcon, Badge, Button, Card, FileButton, Flex, Group, Loader, Paper, Stack, Switch, Text, Title } from '@mantine/core';
import { IconUpload, IconX } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { notifications } from '@mantine/notifications';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { addToHistory } from '@/lib/history-cache';
import { isTerminal, submitScan } from '@/lib/api-client';
import { loadConfig } from '@/lib/config';
import { UploadFormValues, uploadFormSchema } from '@/lib/validators';
import Link from 'next/link';
import { useJobPolling } from '@/hooks/useJobPolling';
import { ResultSummaryCard } from '@/components/ResultSummary';

const config = loadConfig();
const MAX_CACHED_FILE_BYTES = 1024 * 1024; // localStorage is small; keep cached bytes conservative

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const form = useForm<UploadFormValues>({
    resolver: zodResolver(uploadFormSchema),
    defaultValues: { cacheUpload: true }
  });
  const jobQuery = useJobPolling(activeJobId || undefined);

  // When upload starts, react-query will poll; when it finishes, keep the result shown.
  useEffect(() => {
    if (activeJobId && jobQuery.data?.job_id !== activeJobId && jobQuery.data?.job_id) {
      setActiveJobId(jobQuery.data.job_id);
    }
  }, [activeJobId, jobQuery.data?.job_id]);

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
      setActiveJobId(data.job_id);
      queryClient.invalidateQueries({ queryKey: ['api-key-info'] });
      const shouldPersistBytes = variables.cacheUpload && config.featureHistory;
      let encoded: string | undefined;
      if (shouldPersistBytes && variables.file) {
        if (variables.file.size > MAX_CACHED_FILE_BYTES) {
          notifications.show({
            title: 'Upload cached without bytes',
            message: `File is ${(variables.file.size / (1024 * 1024)).toFixed(1)}MB; too large to store in browser storage.`,
            color: 'yellow'
          });
        } else {
          const buffer = await variables.file.arrayBuffer();
          encoded = arrayBufferToBase64(buffer);
        }
      }
      if (config.featureHistory) {
        addToHistory(
          {
            jobId: data.job_id,
            fileName: variables.file?.name ?? 'unknown',
            mimeType: variables.file?.type ?? 'application/octet-stream',
            size: variables.file?.size ?? 0,
            startedAt: data.scanned_at ?? new Date().toISOString(),
            verdict: isTerminal(data.status) ? data.status : undefined,
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
                checked={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
                name={field.name}
                disabled={mutation.isPending || !config.featureHistory}
                
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

      {activeJobId && (
        <Card withBorder>
          <Stack gap="sm">
            <Group justify="space-between" align="center">
              <Title order={4}>Latest results</Title>
              <Badge color="gray">Job {activeJobId}</Badge>
            </Group>
            {jobQuery.isLoading ? (
              <Group gap="sm" align="center">
                <Loader size="sm" />
                <Text size="sm">Fetching status…</Text>
              </Group>
            ) : jobQuery.data ? (
              <Stack gap="xs">
                {jobQuery.isFetching && (
                  <Text size="xs" c="dimmed">
                    Refreshing…
                  </Text>
                )}
                <ResultSummaryCard summary={jobQuery.data} />
              </Stack>
            ) : jobQuery.error ? (
              <Text c="red">Could not fetch status: {jobQuery.error.message}</Text>
            ) : (
              <Text size="sm" c="dimmed">
                Waiting for status…
              </Text>
            )}
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
