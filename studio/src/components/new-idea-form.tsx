'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { SOURCE_LABELS, SOURCES } from '@/lib/content-model'
import { apiUrl } from '@/lib/base-path'

export function NewIdeaForm() {
  const router = useRouter()
  const [title, setTitle] = useState('')
  const [sourceText, setSourceText] = useState('')
  const [source, setSource] = useState<string>('text')
  const [tags, setTags] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const response = await fetch(apiUrl('/api/ideas'), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ title, sourceText, source, tags }),
    })

    if (response.ok) {
      const { id } = (await response.json()) as { id: string }
      router.push(`/ideas/${id}`)
      router.refresh()
      return
    }

    const body = await response.json().catch(() => ({ error: 'Не удалось сохранить' }))
    setError(body.error ?? 'Не удалось сохранить')
    setPending(false)
  }

  return (
    <form onSubmit={onSubmit} className="rounded-lg border border-border bg-surface p-5">
      <label htmlFor="title" className="block text-sm font-medium">
        О чём идея
      </label>
      <input
        id="title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Почему агенты ломаются на длинных задачах"
        className="mt-1.5 w-full rounded-md border border-border bg-bg px-3 py-2 outline-none focus:border-accent"
      />

      <label htmlFor="sourceText" className="mt-5 block text-sm font-medium">
        Исходник
      </label>
      <p className="mt-1 text-sm text-muted">
        Рамблинг, транскрипт или пара строк заметки. Сохраняется как есть и дальше не
        редактируется — скиллы ставят ваши материалы выше собственного синтеза.
      </p>
      <textarea
        id="sourceText"
        value={sourceText}
        onChange={(event) => setSourceText(event.target.value)}
        rows={10}
        className="mt-1.5 w-full rounded-md border border-border bg-bg px-3 py-2 font-mono text-sm outline-none focus:border-accent"
      />

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="source" className="block text-sm font-medium">
            Откуда
          </label>
          <select
            id="source"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            className="mt-1.5 w-full rounded-md border border-border bg-bg px-3 py-2 outline-none focus:border-accent"
          >
            {SOURCES.map((value) => (
              <option key={value} value={value}>
                {SOURCE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="tags" className="block text-sm font-medium">
            Теги
          </label>
          <input
            id="tags"
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="ИИ, агенты"
            className="mt-1.5 w-full rounded-md border border-border bg-bg px-3 py-2 outline-none focus:border-accent"
          />
        </div>
      </div>

      {error ? <p className="mt-4 text-sm text-danger">{error}</p> : null}

      <button
        type="submit"
        disabled={pending || !title.trim()}
        className="mt-6 rounded-md bg-accent px-4 py-2 font-medium text-white disabled:opacity-50"
      >
        {pending ? 'Сохраняю…' : 'Сохранить идею'}
      </button>
    </form>
  )
}
