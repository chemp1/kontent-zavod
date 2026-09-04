'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { STATUSES, STATUS_LABELS, type Status } from '@/lib/content-model'
import { apiUrl } from '@/lib/base-path'

export function StatusSelect({ id, status }: { id: string; status: Status }) {
  const router = useRouter()
  const [value, setValue] = useState<Status>(status)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function change(next: Status) {
    const previous = value
    setValue(next)
    setPending(true)
    setError(null)

    const response = await fetch(apiUrl(`/api/ideas/${id}/status`), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ status: next }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({ error: 'Не удалось' }))
      setError(body.error ?? 'Не удалось')
      setValue(previous)
      setPending(false)
      return
    }

    setPending(false)
    router.refresh()
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={value}
        disabled={pending}
        onChange={(event) => change(event.target.value as Status)}
        className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent disabled:opacity-50"
        aria-label="Статус идеи"
      >
        {STATUSES.map((option) => (
          <option key={option} value={option}>
            {STATUS_LABELS[option]}
          </option>
        ))}
      </select>
      {error ? <span className="text-sm text-danger">{error}</span> : null}
    </div>
  )
}
