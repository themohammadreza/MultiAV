import type { Metadata } from 'next';
import { ColorSchemeScript } from '@mantine/core';
import { Providers } from './providers';
import { AppLayout } from '@/components/AppLayout';

export const metadata: Metadata = {
  title: 'MultiAV Frontend',
  description: 'Upload, scan, and view results'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <ColorSchemeScript />
      </head>
      <body>
        <Providers>
          <AppLayout>{children}</AppLayout>
        </Providers>
      </body>
    </html>
  );
}
