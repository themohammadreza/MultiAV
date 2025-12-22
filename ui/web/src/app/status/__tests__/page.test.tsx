import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Mock } from 'vitest';
import { vi } from 'vitest';

import StatusPage from '../page';
import { fetchRecentJobs } from '@/lib/api-client';
import { useJobPolling } from '@/hooks/useJobPolling';

const pushMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => '/status'
}));

vi.mock('@/hooks/useJobPolling', () => ({
  useJobPolling: vi.fn()
}));

vi.mock('@/lib/api-client', () => ({
  fetchRecentJobs: vi.fn(),
  fetchActiveEngines: vi.fn().mockResolvedValue({ engines: [] })
}));

describe('StatusPage recent job autocomplete', () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  function renderPage() {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <MantineProvider>
          <StatusPage />
        </MantineProvider>
      </QueryClientProvider>
    );
  }

  it('filters recent jobs as the user types', async () => {
    const mockedFetch = fetchRecentJobs as unknown as Mock;
    mockedFetch.mockResolvedValue({
      count: 2,
      items: [
        { job_id: '11111111-1111-4111-8111-111111111111', status: 'done' },
        { job_id: '22222222-2222-4222-8222-222222222222', status: 'done' }
      ]
    });

    (useJobPolling as unknown as Mock).mockReturnValue({ data: undefined, error: null, validationError: null });

    renderPage();

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    const input = await screen.findByPlaceholderText(/search or enter a job uuid/i);
    fireEvent.change(input, { target: { value: '1111' } });

    expect(await screen.findByText('11111111-1111-4111-8111-111111111111')).toBeInTheDocument();
    expect(screen.queryByText('22222222-2222-4222-8222-222222222222')).not.toBeInTheDocument();
  });

  it('navigates to results when selecting a recent job', async () => {
    const mockedFetch = fetchRecentJobs as unknown as Mock;
    mockedFetch.mockResolvedValue({
      count: 1,
      items: [{ job_id: '33333333-3333-4333-8333-333333333333', status: 'done' }]
    });

    (useJobPolling as unknown as Mock).mockReturnValue({ data: undefined, error: null, validationError: null });

    renderPage();

    await screen.findByPlaceholderText(/search or enter a job uuid/i);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    const input = await screen.findByPlaceholderText(/search or enter a job uuid/i);
    fireEvent.change(input, { target: { value: '3333' } });

    const option = await screen.findByText('33333333-3333-4333-8333-333333333333');
    fireEvent.click(option);

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/results/33333333-3333-4333-8333-333333333333'));
  });
});
