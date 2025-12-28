import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import '../styles/globals.css';

import type { Metadata } from 'next';
import { ColorSchemeScript } from '@mantine/core';
import { Providers } from './providers';
import { AppLayout } from '@/components/AppLayout';

export const metadata: Metadata = {
  title: 'MultiAV Admin',
  description: 'Administer API keys and audit scans',
  icons: {
    icon: [
      {
        url: '/greenweb.svg',
        type: 'image/svg+xml',
        sizes: 'any'
      }
    ],
    shortcut: '/greenweb.svg',
    apple: '/greenweb.svg'
  }
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
