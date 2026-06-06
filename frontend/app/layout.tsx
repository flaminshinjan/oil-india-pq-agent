import './globals.css';
import './strata.css';
import './components.css';
import type { Metadata } from 'next';
import { Newsreader, Hanken_Grotesk } from 'next/font/google';

const serif = Newsreader({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--strata-serif',
  display: 'swap',
});
const sans = Hanken_Grotesk({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--strata-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Strata · intelligence OS — Oil India',
  description: 'Advisory intelligence layer for Oil India Limited',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
