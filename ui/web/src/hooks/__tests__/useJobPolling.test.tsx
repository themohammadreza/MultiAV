import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
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

vi.mock('@/lib/api-client', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client')>('@/lib/api-client');
  return {
    ...actual,
    fetchJobResult: vi.fn()
  };
});

import { ApiError, fetchJobResult } from '@/lib/api-client';
import { useJobPolling } from '../useJobPolling';

function Wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient();
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function HookConsumer({ jobId }: { jobId: string }) {
  const { error, isLoading } = useJobPolling(jobId);
  return (
    <div>
      <div data-testid="error">{error?.message}</div>
      <div data-testid="loading">{String(isLoading)}</div>
    </div>
  );
}

describe('useJobPolling', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('stops polling and keeps the error visible for 4xx responses', async () => {
    const mockedFetch = fetchJobResult as unknown as Mock;
    mockedFetch.mockRejectedValue(new ApiError('Not found', 404));

    render(
      <Wrapper>
        <HookConsumer jobId="11111111-1111-4111-8111-111111111111" />
      </Wrapper>
    );

    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('Not found'));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));

    await new Promise((resolve) => setTimeout(resolve, 200));

    expect(mockedFetch).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('error')).toHaveTextContent('Not found');
  });
});
