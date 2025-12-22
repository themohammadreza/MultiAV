import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';

import { ResultSummaryCard } from '../ResultSummary';
import type { ResultSummary } from '@/lib/api-types';

describe('ResultSummaryCard', () => {
  const summary: ResultSummary = {
    job_id: 'job-1',
    status: 'done',
    verdict: 'malicious',
    severity: 'high',
    confidence: 92,
    started_at: '2024-01-01T00:00:00Z',
    completed_at: '2024-01-01T00:05:00Z',
    details: {
      clamav: {
        status: 'done',
        verdict: 'malicious',
        severity: 'high',
        confidence: 88,
        duration: 1234
      }
    }
  };

  it('title-cases verdict and severity for summary and engine rows', () => {
    render(
      <MantineProvider>
        <ResultSummaryCard summary={summary} />
      </MantineProvider>
    );

    expect(screen.getByRole('heading', { level: 3, name: 'Malicious' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'High' })).toBeInTheDocument();
    expect(screen.getAllByText('Malicious').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('High').length).toBeGreaterThanOrEqual(2);
  });

  it('keeps raw values intact for downloads', () => {
    render(
      <MantineProvider>
        <ResultSummaryCard summary={summary} />
      </MantineProvider>
    );

    const downloadLink = screen.getByRole('link', { name: /download raw json/i });
    const href = downloadLink.getAttribute('href');
    expect(href).toBeTruthy();
    if (!href) return;

    const [, encoded] = href.split(',');
    const decoded = decodeURIComponent(encoded);
    expect(decoded).toContain('"verdict": "malicious"');
    expect(decoded).toContain('"severity": "high"');
  });
});
