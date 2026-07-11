import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'DealScout',
  description: 'Find the best deal across Indian shopping sites.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--bg)] text-[var(--text)] antialiased">
        {children}
      </body>
    </html>
  )
}
