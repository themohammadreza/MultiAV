import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { Mock } from 'vitest';
import { vi } from 'vitest';

import { AppLayout } from '../AppLayout';
import { fetchApiKeyStatus } from '../../lib/api-client';

vi.mock('next/navigation', () => ({
  usePathname: () => '/'
}));

vi.mock('../../lib/api-client', () => ({
  fetchApiKeyStatus: vi.fn()
}));

vi.mock('../../lib/api-key', () => ({
  getApiKey: () => 'test-key',
  setApiKey: vi.fn(),
  clearApiKey: vi.fn()
}));

describe('AppLayout', () => {
  it('renders API key owner with remaining tokens', async () => {
    const mockedFetch = fetchApiKeyStatus as unknown as Mock;
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
});
