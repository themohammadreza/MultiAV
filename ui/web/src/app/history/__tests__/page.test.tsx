import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { Mock } from 'vitest';
import { vi } from 'vitest';

import HistoryPage from '../page';
import { fetchRecentJobs } from '@/lib/api-client';

vi.mock('@/lib/api-client', () => ({
  fetchRecentJobs: vi.fn()
}));

describe('HistoryPage', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders server-backed history and omits client cache UI', async () => {
    const mockedFetch = fetchRecentJobs as unknown as Mock;
    mockedFetch.mockResolvedValue({
      count: 1,
      items: [
        {
          job_id: 'job-123',
          status: 'done',
          verdict: 'clean',
          severity: 'low',
          filename: 'archive.zip',
          started_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:00:10Z'
        }
      ]
    });

    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MantineProvider>
          <HistoryPage />
        </MantineProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('job-123')).toBeInTheDocument();
    expect(await screen.findByText('archive.zip')).toBeInTheDocument();
    expect(screen.getByText(/recent jobs \(server\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/cached uploads/i)).not.toBeInTheDocument();
  });

  it('formats status fields in title case while leaving filename untouched', async () => {
    const mockedFetch = fetchRecentJobs as unknown as Mock;
    mockedFetch.mockResolvedValue({
      count: 1,
      items: [
        {
          job_id: 'job-456',
          status: 'done_with_errors',
          verdict: 'malicious',
          severity: 'n/a',
          filename: 'example_file.zip',
          started_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:00:10Z'
        }
      ]
    });

    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MantineProvider>
          <HistoryPage />
        </MantineProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText('job-456')).toBeInTheDocument();
    expect(screen.getByText('example_file.zip')).toBeInTheDocument();
    expect(screen.getByText('Done With Errors')).toBeInTheDocument();
    expect(screen.getByText('Malicious')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument();
  });
});
