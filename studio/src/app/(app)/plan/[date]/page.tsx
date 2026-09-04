import Link from 'next/link'
import { notFound } from 'next/navigation'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { CopyPostButton } from '@/components/copy-post-button'
import { SlotEditor, type IdeaOption } from '@/components/slot-editor'
import { ThreadsPreview } from '@/components/threads-preview'
import { Badge, EmptyState, PageHeader, formatDate } from '@/components/ui'
import { PLATFORM_LABELS, STATUS_LABELS } from '@/lib/content-model'
import { listIdeas, readMaterial } from '@/lib/content'
import {
  SLOT_STATE_LABELS,
  buildDayPlan,
  isValidDate,
  readRhythm,
  rubricLabel,
  weekStart,
  type PlannedSlot,
  type Rubric,
  type SlotState,
} from '@/lib/plan'
import { loadStudioConfig, type StudioAuthor } from '@/lib/studio-config'

export const dynamic = 'force-dynamic'

const STATE_TONES: Record<SlotState, 'neutral' | 'accent' | 'ok' | 'warn'> = {
  empty: 'neutral',
  'needs-draft': 'warn',
  draft: 'accent',
  published: 'ok',
}

export default async function PlanDayPage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params
  if (!isValidDate(date)) notFound()

  const day = buildDayPlan(date)
  const rhythm = readRhythm()
  const { author } = loadStudioConfig()
  const ideas: IdeaOption[] = listIdeas()
    .filter((idea) => idea.status !== 'rejected')
    .map((idea) => ({ id: idea.id, title: idea.title, status: STATUS_LABELS[idea.status] }))

  return (
    <div className="space-y-6">
      <PageHeader
        title={formatDate(date)}
        description="Слоты дня. Бледные предлагает ритм — их ещё не заводили."
        actions={
          <Link href={`/plan?week=${weekStart(date)}`} className="text-sm text-muted hover:text-text">
            ← В календарь
          </Link>
        }
      />

      {day.slots.length === 0 ? (
        <EmptyState
          title="На этот день ничего не запланировано"
          hint="Ритм на этот день пуст — заведите слот руками или поправьте content/plan/rhythm.md."
        />
      ) : (
        <ul className="space-y-4">
          {day.slots.map((slot, index) => (
            <li
              key={slot.id ?? `ghost-${index}`}
              className={
                slot.ghost
                  ? 'rounded-lg border border-dashed border-border p-5'
                  : 'rounded-lg border border-border bg-surface p-5'
              }
            >
              <SlotCard slot={slot} rubrics={rhythm.rubrics} ideas={ideas} author={author} />
            </li>
          ))}
        </ul>
      )}

      <div className="rounded-lg border border-dashed border-border p-5">
        <SlotEditor
          trigger="+ Добавить слот"
          ideas={ideas}
          rubrics={rhythm.rubrics}
          slot={{
            id: null,
            date,
            time: '12:00',
            platform: 'telegram',
            rubric: '',
            ideaId: '',
            note: '',
          }}
        />
      </div>
    </div>
  )
}

function SlotCard({
  slot,
  rubrics,
  ideas,
  author,
}: {
  slot: PlannedSlot
  rubrics: Rubric[]
  ideas: IdeaOption[]
  author: StudioAuthor
}) {
  const rubric = slot.rubric ? rubricLabel(rubrics, slot.rubric) : ''
  const name = slot.material || slot.platform
  const kind = slot.state === 'published' ? 'published' : 'draft'
  const material =
    slot.ideaId && (slot.state === 'draft' || slot.state === 'published')
      ? readMaterial(slot.ideaId, kind, name)
      : null

  const overLimit = slot.limit !== null && slot.chars > slot.limit

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-serif text-lg font-medium">{PLATFORM_LABELS[slot.platform]}</span>
        <span className="text-sm text-muted">{slot.time}</span>
        {rubric ? <Badge tone="neutral">{rubric}</Badge> : null}
        {slot.ghost ? (
          <Badge tone="neutral">по ритму</Badge>
        ) : (
          <Badge tone={STATE_TONES[slot.state]}>{SLOT_STATE_LABELS[slot.state]}</Badge>
        )}
        {slot.chars > 0 ? (
          <span className={`text-xs ${overLimit ? 'text-danger' : 'text-muted'}`}>
            {slot.chars}
            {slot.limit !== null ? ` / ${slot.limit}` : ''} знаков
          </span>
        ) : null}
        <span className="ml-auto flex items-center gap-3">
          {material ? <CopyPostButton markdown={material.body} /> : null}
          {slot.url ? (
            <a
              href={slot.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-accent underline"
            >
              Публикация ↗
            </a>
          ) : null}
        </span>
      </div>

      {slot.ideaId ? (
        <p className="mt-2 text-sm">
          <Link href={`/ideas/${slot.ideaId}`} className="text-accent underline">
            {slot.ideaTitle || slot.ideaId}
          </Link>
          {slot.state === 'needs-draft' ? (
            <span className="text-muted"> — текста под эту площадку ещё нет</span>
          ) : null}
        </p>
      ) : null}

      {slot.note ? <p className="mt-2 text-sm text-muted">{slot.note}</p> : null}

      {material ? (
        slot.platform === 'threads' ? (
          <ThreadsPreview body={material.body} author={author} />
        ) : (
          <div className="prose-post mt-4">
            <Markdown remarkPlugins={[remarkGfm]}>{material.body}</Markdown>
          </div>
        )
      ) : null}

      <div className="mt-3">
        <SlotEditor
          trigger={slot.ghost ? 'Завести слот' : 'Изменить'}
          ideas={ideas}
          rubrics={rubrics}
          slot={{
            id: slot.id,
            date: slot.date,
            time: slot.time,
            platform: slot.platform,
            rubric: slot.rubric,
            ideaId: slot.ideaId,
            note: slot.note,
          }}
        />
      </div>
    </>
  )
}
