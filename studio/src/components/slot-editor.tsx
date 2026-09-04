'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { apiUrl } from '@/lib/base-path'
import { PLATFORMS, PLATFORM_LABELS, type Platform } from '@/lib/content-model'

/**
 * Форма слота: завести, перенести, привязать идею, снять.
 *
 * Редактирование живёт на странице дня, а не в недельной сетке: в сетке 49
 * ячеек, и по форме в каждой означало бы 49 клиентских компонентов со списком
 * идей внутри каждого. День отвечает на тот же вопрос дешевле.
 */

export interface IdeaOption {
  id: string
  title: string
  status: string
}

export interface RubricOption {
  key: string
  label: string
}

export interface SlotDraft {
  id: string | null
  date: string
  time: string
  platform: Platform
  rubric: string
  ideaId: string
  note: string
}

export function SlotEditor({
  slot,
  ideas,
  rubrics,
  trigger,
}: {
  slot: SlotDraft
  ideas: IdeaOption[]
  rubrics: RubricOption[]
  trigger: string
}) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(slot)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof SlotDraft>(key: K, value: SlotDraft[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function send(method: 'POST' | 'PATCH' | 'DELETE') {
    setPending(true)
    setError(null)

    const url =
      method === 'POST' ? apiUrl('/api/plan/slots') : apiUrl(`/api/plan/slots/${form.id}`)
    const response = await fetch(url, {
      method,
      headers: { 'content-type': 'application/json' },
      ...(method === 'DELETE' ? {} : { body: JSON.stringify(form) }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => ({ error: 'Не удалось' }))
      setError(body.error ?? 'Не удалось')
      setPending(false)
      return
    }

    setPending(false)
    setOpen(false)
    router.refresh()
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-sm text-accent hover:underline"
      >
        {trigger}
      </button>
    )
  }

  return (
    <form
      className="mt-3 space-y-3 rounded-lg border border-border bg-surface-2 p-4"
      onSubmit={(event) => {
        event.preventDefault()
        void send(form.id ? 'PATCH' : 'POST')
      }}
    >
      <div className="flex flex-wrap gap-3">
        <Field label="Дата">
          <input
            type="date"
            value={form.date}
            onChange={(event) => set('date', event.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Время">
          <input
            type="time"
            value={form.time}
            onChange={(event) => set('time', event.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Площадка">
          <select
            value={form.platform}
            onChange={(event) => set('platform', event.target.value as Platform)}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
          >
            {PLATFORMS.map((platform) => (
              <option key={platform} value={platform}>
                {PLATFORM_LABELS[platform]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Рубрика">
          <select
            value={form.rubric}
            onChange={(event) => set('rubric', event.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
          >
            <option value="">без рубрики</option>
            {rubrics.map((rubric) => (
              <option key={rubric.key} value={rubric.key}>
                {rubric.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Идея">
        <select
          value={form.ideaId}
          onChange={(event) => set('ideaId', event.target.value)}
          className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        >
          <option value="">не выбрана</option>
          {ideas.map((idea) => (
            <option key={idea.id} value={idea.id}>
              {idea.title} · {idea.status}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Заметка">
        <textarea
          value={form.note}
          onChange={(event) => set('note', event.target.value)}
          rows={2}
          placeholder="О чём этот слот, пока идея не выбрана"
          className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        />
      </Field>

      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {form.id ? 'Сохранить' : 'Завести слот'}
        </button>
        <button
          type="button"
          onClick={() => {
            setForm(slot)
            setError(null)
            setOpen(false)
          }}
          className="text-sm text-muted hover:text-text"
        >
          Отмена
        </button>
        {form.id ? (
          <button
            type="button"
            disabled={pending}
            onClick={() => void send('DELETE')}
            className="ml-auto text-sm text-danger hover:underline disabled:opacity-60"
          >
            Снять слот
          </button>
        ) : null}
      </div>
    </form>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      {children}
    </label>
  )
}
