import Link from 'next/link'

import { NavLink } from '@/components/nav-link'
import { gitStatus } from '@/lib/git'

// Состояние git проверяется на каждый запрос: `git init` в корне должен
// снять баннер без перезапуска.
export const dynamic = 'force-dynamic'

const SECTIONS = [
  { href: '/plan', label: 'Контент-план' },
  { href: '/inbox', label: 'Входящие' },
  { href: '/library', label: 'Библиотека' },
  { href: '/skill', label: 'Карта скилла' },
  { href: '/memory', label: 'Память' },
  { href: '/reports', label: 'Отчёты' },
  { href: '/telegram', label: 'Telegram' },
  { href: '/projects', label: 'Проекты' },
]

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const git = await gitStatus()

  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
          <Link href="/library" className="font-serif text-lg font-semibold tracking-tight">
            Студия
          </Link>
          <nav className="flex flex-wrap items-center gap-1">
            {SECTIONS.map((section) => (
              <NavLink key={section.href} href={section.href}>
                {section.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      {!git.available ? (
        <div className="border-b border-border bg-warn-soft">
          <p className="mx-auto w-full max-w-6xl px-5 py-2 text-sm text-warn">
            История версий и коммиты выключены: {git.reason}. Файлы сохраняются, но в git не
            попадают.
          </p>
        </div>
      ) : null}
      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8">{children}</main>
    </div>
  )
}
