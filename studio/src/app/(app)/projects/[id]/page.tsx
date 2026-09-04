import Link from 'next/link'
import { notFound } from 'next/navigation'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Badge, EmptyState, PageHeader, formatDate } from '@/components/ui'
import { listProjectDays, projectTotals, readProject } from '@/lib/projects'
import { PROJECT_STATUS_LABELS } from '@/lib/projects-model'
import { loadStudioConfig } from '@/lib/studio-config'

export const dynamic = 'force-dynamic'

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  let project
  try {
    project = readProject(id)
  } catch {
    // assertValidId бросает на мусорном слаге из адресной строки.
    notFound()
  }
  if (!project) notFound()

  const days = listProjectDays(project.id)
  const totals = projectTotals(project.id, 30)
  const findingsDir = loadStudioConfig().data.projectFindings

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader
        title={project.title}
        description={project.watch}
        actions={<Badge tone="neutral">{PROJECT_STATUS_LABELS[project.status]}</Badge>}
      />

      <section className="space-y-3">
        <dl className="grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-[auto_1fr]">
          {project.urgent ? (
            <>
              <dt className="text-muted">Что срочно</dt>
              <dd>{project.urgent}</dd>
            </>
          ) : null}
          <dt className="text-muted">Чатов в теме</dt>
          <dd className="font-mono tabular-nums">{project.chatCount}</dd>
          <dt className="text-muted">За месяц</dt>
          <dd className="font-mono tabular-nums">
            находок {totals.findings}, срочных {totals.urgent}
          </dd>
          {project.since ? (
            <>
              <dt className="text-muted">С какого дня</dt>
              <dd>{formatDate(project.since)}</dd>
            </>
          ) : null}
        </dl>
      </section>

      {project.body ? (
        <article className="prose-post scroll-x">
          <Markdown remarkPlugins={[remarkGfm]}>{project.body}</Markdown>
        </article>
      ) : null}

      <section className="space-y-4">
        <h2 className="font-serif text-lg font-medium">Обзоры по дням</h2>
        {days.length === 0 ? (
          <EmptyState
            title="Обзоров пока нет"
            hint={
              <>
                Их кладёт внешний наблюдатель в{' '}
                <code>{findingsDir}/&lt;проект&gt;/&lt;дата&gt;.md</code> — мимо git: это
                содержимое чужих чатов. Папка задаётся в <code>studio.json</code>.
              </>
            }
          />
        ) : (
          <ul className="space-y-3">
            {days.map((day) => (
              <li key={day.date}>
                <Link
                  href={`/projects/${project.id}/${day.date}`}
                  className="block rounded-lg border border-border bg-surface p-4 transition-colors hover:border-accent"
                >
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="font-medium">{formatDate(day.date)}</span>
                    {day.urgent > 0 ? <Badge tone="warn">срочных: {day.urgent}</Badge> : null}
                  </div>
                  {day.summary ? <p className="mt-1.5 text-sm text-muted">{day.summary}</p> : null}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="mt-12 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-5 text-sm text-muted">
        <Link href="/projects" className="text-accent underline">
          Все проекты
        </Link>
        <code className="font-mono text-xs">{project.relPath}</code>
      </footer>
    </div>
  )
}
