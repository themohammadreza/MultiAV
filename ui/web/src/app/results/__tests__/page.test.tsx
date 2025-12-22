import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { Mock } from 'vitest';
import { vi } from 'vitest';

vi.mock('@/lib/config', () => ({
  loadConfig: () => ({
    apiBaseUrl: '',
    uploadSizeLimitMb: 50,
    pollIntervalMs: 20,
    pollTimeoutMs: 1000
  })
}));

import ResultPage from '../[jobId]/page';
import { ApiError, fetchJobResult } from '@/lib/api-client';

vi.mock('next/navigation', () => ({
  useParams: () => ({ jobId: '11111111-1111-4111-8111-111111111111' })
}));

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client');
  return {
    ...actual,
    fetchJobResult: vi.fn()
  };
});

describe('ResultPage', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('keeps the error message visible without resuming loading state', async () => {
    const mockedFetch = fetchJobResult as unknown as Mock;
    mockedFetch.mockRejectedValue(new ApiError('Not found', 404));

    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MantineProvider>
          <ResultPage />
        </MantineProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText('Not found')).toBeInTheDocument());
    expect(screen.queryByText(/loading results/i)).not.toBeInTheDocument();
    expect(mockedFetch).toHaveBeenCalledTimes(1);

    await new Promise((resolve) => setTimeout(resolve, 200));

    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Not found')).toBeInTheDocument();
    expect(screen.queryByText(/loading results/i)).not.toBeInTheDocument();
  });
});
