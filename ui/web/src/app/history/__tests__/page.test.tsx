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
    expect(screen.getByText(/history is sourced from the server/i)).toBeInTheDocument();
    expect(screen.queryByText(/cached uploads/i)).not.toBeInTheDocument();
  });
});
