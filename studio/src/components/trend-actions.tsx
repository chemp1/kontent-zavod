'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { apiUrl } from '@/lib/base-path'

/**
 * Решение по карточке тренда. «Завести идею» кладёт карточку в библиотеку
 * исходником — писать пост всё равно человеку или скиллу, робот до текста
 * не допущен.
 */
export function TrendActions({ slug, status }: { slug: string; status: string }) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send(action: 'idea' | 'skip' | 'reset') {
    setPending(true)
    setError(null)

    const response = await fetch(apiUrl(`/api/trends/${slug}`), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({ error: 'Не удалось' }))
      setError(body.error ?? 'Не удалось')
      setPending(false)
      return
    }

    const body = (await response.json()) as { ideaId?: string }
    setPending(false)
    if (action === 'idea' && body.ideaId) {
      router.push(`/ideas/${body.ideaId}`)
      return
    }
    router.refresh()
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      {status !== 'used' ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => void send('idea')}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
        >
          Завести идею
        </button>
      ) : null}
      {status === 'new' ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => void send('skip')}
          className="text-sm text-muted hover:text-text disabled:opacity-60"
        >
          Мимо
        </button>
      ) : null}
      {status === 'skipped' ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => void send('reset')}
          className="text-sm text-muted hover:text-text disabled:opacity-60"
        >
          Вернуть в ленту
        </button>
      ) : null}
      {error ? <span className="text-sm text-danger">{error}</span> : null}
    </div>
  )
}
