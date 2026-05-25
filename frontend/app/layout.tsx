import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Oil India PQ Assistant',
  description: 'Parliamentary-question response assistant for Oil India Limited',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
