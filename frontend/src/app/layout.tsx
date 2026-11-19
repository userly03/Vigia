import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { MARCA } from '@/lib/marca';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: { default: `${MARCA.nombre} · cables submarinos`, template: `%s · ${MARCA.nombre}` },
  description: MARCA.descripcion,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={inter.variable}>
      <body className={`${inter.className} antialiased`}>
        {children}
      </body>
    </html>
  );
}
