import Link from 'next/link'

import { Badge, EmptyState, PageHeader, StatusBadge, formatDate } from '@/components/ui'
import {
  PLATFORM_LABELS,
  SOURCE_LABELS,
  STATUSES,
  STATUS_LABELS,
  type Platform,
  type Status,
  listIdeas,
} from '@/lib/content'

export const dynamic = 'force-dynamic'

function platformLabel(name: string): string {
  if (name === 'master') return 'Мастер'
  return PLATFORM_LABELS[name as Platform] ?? name
}

export default async function LibraryPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>
}) {
  const { status: statusFilter } = await searchParams
  const all = listIdeas()
  const ideas =
    statusFilter && (STATUSES as readonly string[]).includes(statusFilter)
      ? all.filter((idea) => idea.status === statusFilter)
      : all

  const counts = new Map<Status, number>()
  for (const idea of all) counts.set(idea.status, (counts.get(idea.status) ?? 0) + 1)

  return (
    <>
      <PageHeader
        title="Библиотека"
        description="Все идеи и всё, что из них выросло: черновики, адаптации, публикации."
        actions={
          <Link
            href="/inbox"
            className="rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-white"
          >
            Новая идея
          </Link>
        }
      />

      <div className="mb-6 flex flex-wrap gap-2">
        <FilterChip href="/library" active={!statusFilter} label={`Все (${all.length})`} />
        {STATUSES.filter((status) => counts.has(status)).map((status) => (
          <FilterChip
            key={status}
            href={`/library?status=${status}`}
            active={statusFilter === status}
            label={`${STATUS_LABELS[status]} (${counts.get(status)})`}
          />
        ))}
      </div>

      {ideas.length === 0 ? (
        <EmptyState
          title={statusFilter ? 'В этом статусе пусто' : 'Пока ни одной идеи'}
          hint={
            statusFilter ? (
              <Link href="/library" className="text-accent underline">
                Показать все
              </Link>
            ) : (
              <>
                Идея — это исходная мысль или рамблинг, из которого потом вырастают посты.
                Начните с <Link href="/inbox" className="text-accent underline">входящих</Link>.
              </>
            )
          }
        />
      ) : (
        <ul className="space-y-3">
          {ideas.map((idea) => (
            <li key={idea.id}>
              <Link
                href={`/ideas/${idea.id}`}
                className="block rounded-lg border border-border bg-surface p-4 transition-colors hover:border-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={idea.status} />
                  <span className="font-serif text-lg font-medium">{idea.title}</span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
                  <span>{formatDate(idea.created)}</span>
                  <span>{SOURCE_LABELS[idea.source]}</span>
                  {idea.tags.length > 0 ? <span>{idea.tags.join(', ')}</span> : null}
                </div>

                {idea.drafts.length > 0 || idea.published.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {idea.drafts.map((material) => (
                      <Badge key={`d-${material.name}`} tone="neutral">
                        {platformLabel(material.name)}
                      </Badge>
                    ))}
                    {idea.published.map((material) => (
                      <Badge key={`p-${material.name}`} tone="ok">
                        {platformLabel(material.name)} · опубликовано
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

function FilterChip({
  href,
  active,
  label,
}: {
  href: string
  active: boolean
  label: string
}) {
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
