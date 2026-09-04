import Link from 'next/link'

import { Badge, Card, EmptyState, PageHeader, formatDate } from '@/components/ui'
import { listProjects, projectTotals } from '@/lib/projects'
import { PROJECT_STATUS_LABELS, type ProjectStatus } from '@/lib/projects-model'

export const dynamic = 'force-dynamic'

const STATUS_TONES: Record<ProjectStatus, 'ok' | 'warn' | 'neutral'> = {
  active: 'ok',
  paused: 'warn',
  proposed: 'neutral',
}

export default function ProjectsPage() {
  const projects = listProjects()

  return (
    <div className="space-y-8">
      <PageHeader
        title="Проекты"
        description="Темы, за которыми следим в Telegram. Срочное прилетает карточкой в бота сразу, остальное копится и выходит обзором раз в сутки."
      />

      {projects.length === 0 ? (
        <EmptyState
          title="Тем пока нет"
          hint="Тема появляется здесь сама, как только в content/telegram/projects/ ложится markdown-файл. Пересборка не нужна."
        />
      ) : (
        <ul className="space-y-4">
          {projects.map((project) => {
            const totals = projectTotals(project.id)
            return (
              <li key={project.id}>
                <Card>
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <Link
                      href={`/projects/${project.id}`}
                      className="font-serif text-lg font-medium hover:text-accent"
                    >
                      {project.title}
                    </Link>
                    <div className="flex items-center gap-2">
                      {totals.urgent > 0 ? <Badge tone="warn">срочных: {totals.urgent}</Badge> : null}
                      <Badge tone={STATUS_TONES[project.status]}>
                        {PROJECT_STATUS_LABELS[project.status]}
                      </Badge>
                    </div>
                  </div>

                  <dl className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-[auto_1fr]">
                    {project.watch ? (
                      <>
                        <dt className="text-muted">За чем следим</dt>
                        <dd>{project.watch}</dd>
                      </>
                    ) : null}
                    <dt className="text-muted">Чатов</dt>
                    <dd className="font-mono tabular-nums">{project.chatCount}</dd>
                    <dt className="text-muted">За неделю</dt>
                    <dd className="font-mono tabular-nums">
                      {totals.findings > 0 ? `находок ${totals.findings}` : 'пока пусто'}
                      {totals.lastDay ? (
                        <span className="ml-2 font-sans text-muted">
                          последняя сводка {formatDate(totals.lastDay)}
                        </span>
                      ) : null}
                    </dd>
                  </dl>

                  <code className="mt-3 block font-mono text-xs text-muted">{project.relPath}</code>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
