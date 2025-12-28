import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ImgHTMLAttributes } from 'react';
import type { Mock } from 'vitest';
import { vi } from 'vitest';

import { AppLayout } from '../AppLayout';
import { fetchApiKeyStatus, fetchHealth } from '../../lib/api-client';

vi.mock('next/navigation', () => ({
  usePathname: () => '/'
}));

vi.mock('next/image', () => ({
  default: ({ priority, unoptimized, ...props }: ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean; unoptimized?: boolean }) => (
    <img {...props} />
  )
}));

vi.mock('../../lib/api-client', () => ({
  fetchApiKeyStatus: vi.fn(),
  fetchHealth: vi.fn()
}));

vi.mock('../../lib/api-key', () => ({
  getApiKey: () => 'test-key',
  setApiKey: vi.fn(),
  clearApiKey: vi.fn()
}));

describe('AppLayout', () => {
  it('renders API key owner with remaining tokens', async () => {
    const mockedHealth = fetchHealth as unknown as Mock;
    const mockedFetch = fetchApiKeyStatus as unknown as Mock;
    mockedHealth.mockResolvedValue({ status: 'ok' });
    mockedFetch.mockResolvedValue({
      bypassed: false,
      name: 'majid',
      days_remaining: 12,
      requests_remaining_today: 8
    });

    const client = new QueryClient();

    render(
      <QueryClientProvider client={client}>
        <MantineProvider>
          <AppLayout>
            <div>content</div>
          </AppLayout>
        </MantineProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText(/majid/)).toBeInTheDocument());
    expect(screen.getByText(/12 day\(s\) left/)).toBeInTheDocument();
    expect(screen.getByText(/8 request\(s\) left today/)).toBeInTheDocument();
  });

  it('shows warmup message until health is ready', async () => {
    const mockedHealth = fetchHealth as unknown as Mock;
    mockedHealth.mockRejectedValueOnce(new Error('connection refused'));

    const client = new QueryClient();

    render(
      <QueryClientProvider client={client}>
        <MantineProvider>
          <AppLayout>
            <div>content</div>
          </AppLayout>
        </MantineProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText(/warming up/i)).toBeInTheDocument();
  });

  it('renders the GreenWeb logo next to the title', async () => {
    const mockedHealth = fetchHealth as unknown as Mock;
    mockedHealth.mockResolvedValue({ status: 'ok' });

    const client = new QueryClient();

    render(
      <QueryClientProvider client={client}>
        <MantineProvider>
          <AppLayout>
            <div>content</div>
          </AppLayout>
        </MantineProvider>
      </QueryClientProvider>
    );

    const logo = await screen.findByAltText('GreenWeb logo');
    expect(logo).toHaveAttribute('src', '/greenweb.svg');
  });
});
