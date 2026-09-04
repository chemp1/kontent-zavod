import Link from 'next/link'

import { Badge, EmptyState, PageHeader, StatusBadge } from '@/components/ui'
import { PLATFORM_LABELS } from '@/lib/content-model'
import {
  SLOT_STATE_LABELS,
  WEEKDAY_LABELS,
  buildWeek,
  rubricLabel,
  unscheduledIdeas,
  type DayPlan,
  type PlannedSlot,
  type Rubric,
  type SlotState,
} from '@/lib/plan'

export const dynamic = 'force-dynamic'

const STATE_TONES: Record<SlotState, 'neutral' | 'accent' | 'ok' | 'warn'> = {
  empty: 'neutral',
  'needs-draft': 'warn',
  draft: 'accent',
  published: 'ok',
}

function formatRange(start: string): string {
  const from = new Date(`${start}T00:00:00Z`)
  const to = new Date(`${start}T00:00:00Z`)
  to.setUTCDate(to.getUTCDate() + 6)
  const fmt = (date: Date, withMonth: boolean) =>
    date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      ...(withMonth ? { month: 'long' } : {}),
      timeZone: 'UTC',
    })
  const sameMonth = from.getUTCMonth() === to.getUTCMonth()
  return `${fmt(from, !sameMonth)} — ${fmt(to, true)}`
}

export default async function PlanPage({
  searchParams,
}: {
  searchParams: Promise<{ week?: string }>
}) {
  const { week } = await searchParams
  const plan = buildWeek(week)
  const queue = unscheduledIdeas()
  const today = new Intl.DateTimeFormat('en-CA').format(new Date())

  return (
    <div className="space-y-8">
      <PageHeader
        title="Контент-план"
        description="Что и когда выходит на каждой площадке. Бледные слоты предлагает ритм — их ещё не заводили. Публикует всё равно человек: календарь отвечает только на вопрос «когда»."
        actions={
          <>
            <Link href="/plan/candidates" className="text-sm text-accent hover:underline">
              Из звонков →
            </Link>
            <Link href="/plan/trends" className="text-sm text-accent hover:underline">
              Тренды →
            </Link>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link
          href={`/plan?week=${plan.previous}`}
          className="rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-text"
        >
          ← Неделя
        </Link>
        <span className="font-serif text-lg font-medium">{formatRange(plan.start)}</span>
        <Link
          href={`/plan?week=${plan.next}`}
          className="rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-text"
        >
          Неделя →
        </Link>
        <Link href="/plan" className="text-sm text-muted hover:text-text">
          Сегодня
        </Link>
      </div>

      {plan.rhythmBroken ? (
        <p className="rounded-lg border border-warn bg-warn-soft px-4 py-3 text-sm text-warn">
          Сетка ритма не прочиталась: в <code>content/plan/rhythm.md</code> сломан фронтматтер.
          Чаще всего это незакавыченное двоеточие в подписи — YAML падает целиком, и календарь
          остаётся без предложений ритма.
        </p>
      ) : null}

      {plan.load.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {plan.load.map((row) => (
            <span
              key={row.platform}
              className="rounded-full border border-border px-3 py-1 text-sm"
              title="Заведено из того, что предлагает ритм; в скобках — сколько уже с текстом"
            >
              <span className="text-muted">{PLATFORM_LABELS[row.platform]}</span>{' '}
              <span className="font-medium">
                {row.planned}/{row.rhythm}
              </span>
              {row.ready > 0 ? <span className="text-ok"> · {row.ready} с текстом</span> : null}
            </span>
          ))}
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <div className="grid min-w-[64rem] grid-cols-7 gap-3">
          {plan.days.map((day) => (
            <DayColumn key={day.date} day={day} rubrics={plan.rubrics} isToday={day.date === today} />
          ))}
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="font-serif text-lg font-medium">Очередь: идеи без даты</h2>
        {queue.length === 0 ? (
          <EmptyState
            title="Очередь пуста"
            hint={
              <>
                Все идеи расставлены по слотам. Новые заводятся во{' '}
                <Link href="/inbox" className="text-accent underline">
                  входящих
                </Link>
                .
              </>
            }
          />
        ) : (
          <ul className="flex flex-wrap gap-2">
            {queue.map((idea) => (
              <li key={idea.id}>
                <Link
                  href={`/ideas/${idea.id}`}
                  className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm transition-colors hover:border-accent"
                >
                  <StatusBadge status={idea.status} />
                  <span>{idea.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function DayColumn({
  day,
  rubrics,
  isToday,
}: {
  day: DayPlan
  rubrics: Rubric[]
  isToday: boolean
}) {
  return (
    <div className="min-w-0">
      <Link
        href={`/plan/${day.date}`}
        className={`mb-2 flex items-baseline justify-between gap-2 border-b pb-1.5 ${
          isToday ? 'border-accent text-accent' : 'border-border'
        }`}
      >
        <span className="font-medium">{WEEKDAY_LABELS[day.weekday]}</span>
        <span className="text-sm text-muted">{day.date.slice(8)}</span>
      </Link>

      <ul className="space-y-2">
        {day.slots.map((slot, index) => (
          <li key={slot.id ?? `ghost-${index}`}>
            <SlotChip slot={slot} rubrics={rubrics} />
          </li>
        ))}
        {day.slots.length === 0 ? <li className="text-sm text-muted">—</li> : null}
      </ul>
    </div>
  )
}

function SlotChip({ slot, rubrics }: { slot: PlannedSlot; rubrics: Rubric[] }) {
  const rubric = slot.rubric ? rubricLabel(rubrics, slot.rubric) : ''

  const body = (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium">{PLATFORM_LABELS[slot.platform]}</span>
        <span className="text-xs text-muted">{slot.time}</span>
      </div>
      <p className="mt-1 line-clamp-3 text-sm">
        {slot.ideaTitle || rubric || slot.note || 'Слот без темы'}
      </p>
      {!slot.ghost ? (
        <div className="mt-2">
          <Badge tone={STATE_TONES[slot.state]}>{SLOT_STATE_LABELS[slot.state]}</Badge>
        </div>
      ) : null}
    </>
  )

  if (slot.ghost) {
    return (
      <Link
        href={`/plan/${slot.date}`}
        className="block rounded-lg border border-dashed border-border p-2.5 text-muted transition-colors hover:border-accent hover:text-text"
      >
        {body}
      </Link>
    )
  }

  return (
    <Link
      href={`/plan/${slot.date}`}
      className="block rounded-lg border border-border bg-surface p-2.5 transition-colors hover:border-accent"
    >
      {body}
    </Link>
  )
}
