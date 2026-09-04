import type { Metadata } from 'next'

import { loadStudioConfig } from '@/lib/studio-config'

import './globals.css'

/** Заголовок вкладки берётся из `content/studio.json`, поэтому не статический. */
export function generateMetadata(): Metadata {
  return {
    title: loadStudioConfig().title,
    description: 'Идеи, черновики и карта скилла авторского голоса',
  }
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-bg text-text">{children}</body>
    </html>
  )
}
