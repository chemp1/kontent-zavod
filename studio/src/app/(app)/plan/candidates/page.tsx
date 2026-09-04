import Link from 'next/link'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { CandidateActions } from '@/components/candidate-actions'
import { Badge, EmptyState, PageHeader, formatDate } from '@/components/ui'
import {
  CANDIDATE_STATUSES,
  CANDIDATE_STATUS_LABELS,
  listCandidates,
  type CandidateStatus,
} from '@/lib/candidates'
import { PLATFORM_LABELS } from '@/lib/content-model'

export const dynamic = 'force-dynamic'

const STATUS_TONES: Record<CandidateStatus, 'accent' | 'ok' | 'neutral'> = {
  pending: 'accent',
  accepted: 'ok',
  rejected: 'neutral',
}

export default async function CandidatesPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>
}) {
  const { status } = await searchParams
  const all = listCandidates()
  const filter = (CANDIDATE_STATUSES as readonly string[]).includes(status ?? '')
    ? (status as CandidateStatus)
    : null
  const candidates = filter ? all.filter((item) => item.status === filter) : all

  return (
    <div className="space-y-6">
      <PageHeader
        title="Идеи из звонков"
        description="Что автор уже сформулировал вслух на своих встречах. Наружу вышла только его прямая речь: чужие реплики и имена собеседников остались в .data/ и в git не попадают."
        actions={
          <Link href="/plan" className="text-sm text-muted hover:text-text">
            ← В календарь
          </Link>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Chip href="/plan/candidates" active={!filter} label={`Все (${all.length})`} />
        {CANDIDATE_STATUSES.map((value) => (
          <Chip
            key={value}
            href={`/plan/candidates?status=${value}`}
            active={filter === value}
            label={`${CANDIDATE_STATUS_LABELS[value]} (${all.filter((c) => c.status === value).length})`}
          />
        ))}
      </div>

      {candidates.length === 0 ? (
        <EmptyState
          title={all.length === 0 ? 'Кандидатов пока нет' : 'В этом срезе пусто'}
          hint={
            all.length === 0 ? (
              <>
                Их кладёт внешний майнер звонков: берёт расшифровки встреч, оставляет только
                реплики автора и ищет мысли для поста. Формат файла — в{' '}
                <code>content/README.md</code>.
              </>
            ) : (
              <Link href="/plan/candidates" className="text-accent underline">
                Показать все
              </Link>
            )
          }
        />
      ) : (
        <ul className="space-y-4">
          {candidates.map((candidate) => (
            <li key={candidate.slug} className="rounded-lg border border-border bg-surface p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={STATUS_TONES[candidate.status]}>
                  {CANDIDATE_STATUS_LABELS[candidate.status]}
                </Badge>
                {candidate.platform ? (
                  <Badge tone="neutral">{PLATFORM_LABELS[candidate.platform]}</Badge>
                ) : null}
                {candidate.date ? (
                  <span className="text-sm text-muted">звонок {formatDate(candidate.date)}</span>
                ) : null}
              </div>

              <h2 className="mt-2 font-serif text-lg font-medium">{candidate.title}</h2>

              {candidate.body ? (
                <div className="prose-post mt-3 text-sm">
                  <Markdown remarkPlugins={[remarkGfm]}>{candidate.body}</Markdown>
                </div>
              ) : null}

              <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-border pt-3">
                <CandidateActions slug={candidate.slug} status={candidate.status} />
                {candidate.ideaId ? (
                  <Link href={`/ideas/${candidate.ideaId}`} className="text-sm text-accent underline">
                    Идея →
                  </Link>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Chip({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <Link
      href={href}
      className={
        active
          ? 'rounded-full bg-accent-soft px-3 py-1 text-sm font-medium text-accent'
          : 'rounded-full border border-border px-3 py-1 text-sm text-muted transition-colors hover:text-text'
      }
    >
      {label}
    </Link>
  )
}
