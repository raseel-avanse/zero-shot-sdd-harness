import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Sentinel — Security Assessment Console',
  description: 'Scope-gated, agentic whitebox security assessment.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas text-ink antialiased selection:bg-primary-tint">
        {children}
      </body>
    </html>
  )
}
