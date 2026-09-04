'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname()
  const active = pathname === href || pathname.startsWith(`${href}/`)

  return (
    <Link
      href={href}
      className={
        active
          ? 'rounded-md bg-accent-soft px-3 py-1.5 text-sm font-medium text-accent'
          : 'rounded-md px-3 py-1.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-text'
      }
    >
      {children}
    </Link>
  )
}
