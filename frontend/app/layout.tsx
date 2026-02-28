import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { Sidebar } from '@/components/layout/Sidebar'

export const metadata: Metadata = {
  title: 'Automated Liquidity Bridging System',
  description: 'Patent Spec v4.0 — Intelligent payment failure prediction and bridge loan orchestration',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased">
        <Providers>
          <Sidebar />
          <div className="pl-56 min-h-screen">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  )
}
