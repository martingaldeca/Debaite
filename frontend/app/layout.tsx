
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Sidebar from '@/components/sidebar'
import { Toaster } from "@/components/ui/toaster"

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Debaite',
  description: 'AI Debate Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-background text-foreground flex`}>
        <Sidebar className="w-64 border-r border-border" />
        <main className="flex-1 overflow-auto ml-64">
          {children}
        </main>
        <Toaster />
      </body>
    </html>
  )
}
