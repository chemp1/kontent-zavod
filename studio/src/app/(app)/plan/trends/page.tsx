import Link from 'next/link'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { TrendActions } from '@/components/trend-actions'
import { Badge, EmptyState, PageHeader, formatDate } from '@/components/ui'
import {
  TREND_KIND_LABELS,
  TREND_STATUSES,
  TREND_STATUS_LABELS,
  isTrendStatus,
  listFeeds,
  listTrends,
  type TrendStatus,
} from '@/lib/trends'

export const dynamic = 'force-dynamic'

const STATUS_TONES: Record<TrendStatus, 'accent' | 'ok' | 'neutral'> = {
  new: 'accent',
  used: 'ok',
  skipped: 'neutral',
}

export default async function TrendsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; source?: string }>
}) {
  const { status, source } = await searchParams
  const feeds = listFeeds()
  const all = listTrends()

  const trends = all.filter(
    (trend) =>
      (!isTrendStatus(status) || trend.status === status) && (!source || trend.source === source),
  )

  const count = (predicate: (source: string, status: TrendStatus) => boolean) =>
    all.filter((trend) => predicate(trend.source, trend.status)).length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Тренды"
        description="Что вышло у фондов и в новостях, суть за три строки и два-три угла под голос автора. Постов робот не пишет: угол — приглашение подумать, а не готовый текст."
        actions={
          <Link href="/plan" className="text-sm text-muted hover:text-text">
            ← В календарь
          </Link>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Chip href="/plan/trends" active={!status && !source} label={`Все (${all.length})`} />
        {TREND_STATUSES.map((value) => (
          <Chip
            key={value}
            href={`/plan/trends?status=${value}`}
            active={status === value && !source}
            label={`${TREND_STATUS_LABELS[value]} (${count((_, s) => s === value)})`}
          />
        ))}
        {feeds.map((feed) => (
          <Chip
            key={feed.id}
            href={`/plan/trends?source=${feed.id}`}
            active={source === feed.id}
            label={`${feed.title} (${count((s) => s === feed.id)})`}
          />
        ))}
      </div>

      {trends.length === 0 ? (
        <EmptyState
          title={all.length === 0 ? 'Карточек пока нет' : 'В этом срезе пусто'}
          hint={
            all.length === 0 ? (
              <>
                Их кладёт внешний сборщик по расписанию: обходит фиды из{' '}
                <code>content/trends/sources.md</code> и оставляет здесь карточки. Формат —
                в <code>content/README.md</code>.
              </>
            ) : (
              <Link href="/plan/trends" className="text-accent underline">
                Показать все
              </Link>
            )
          }
        />
      ) : (
        <ul className="space-y-4">
          {trends.map((trend) => (
            <li key={trend.slug} className="rounded-lg border border-border bg-surface p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={STATUS_TONES[trend.status]}>{TREND_STATUS_LABELS[trend.status]}</Badge>
                <span className="text-sm text-muted">
                  {trend.sourceTitle} · {TREND_KIND_LABELS[trend.kind]}
                </span>
                {trend.published ? (
                  <span className="text-sm text-muted">{formatDate(trend.published)}</span>
                ) : null}
              </div>

              <h2 className="mt-2 font-serif text-lg font-medium">
                <a href={trend.url} target="_blank" rel="noreferrer" className="hover:underline">
                  {trend.title} ↗
                </a>
              </h2>

              {trend.body ? (
                <div className="prose-post mt-3 text-sm">
                  <Markdown remarkPlugins={[remarkGfm]}>{trend.body}</Markdown>
                </div>
              ) : null}

              <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-border pt-3">
                <TrendActions slug={trend.slug} status={trend.status} />
                {trend.ideaId ? (
                  <Link href={`/ideas/${trend.ideaId}`} className="text-sm text-accent underline">
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
