import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'EvoPalantir Web',
  description: 'Next.js web app for the EvoPalantir monorepo',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
