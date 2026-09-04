import Link from 'next/link'
import { notFound } from 'next/navigation'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { ReportBlock } from '@/components/charts'
import { Badge, PageHeader, formatDate } from '@/components/ui'
import { splitBody } from '@/lib/blocks'
import { readProject, readProjectDay } from '@/lib/projects'
import type { Block } from '@/lib/reports-model'

export const dynamic = 'force-dynamic'

export default async function ProjectDayPage({
  params,
}: {
  params: Promise<{ id: string; date: string }>
}) {
  const { id, date } = await params

  let project
  let day
  try {
    project = readProject(id)
    day = readProjectDay(id, date)
  } catch {
    // assertValidId бросает на мусорном слаге или дате из адресной строки.
    notFound()
  }
  if (!project || !day) notFound()

  const parts = splitBody(day.body, day.blocks)

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={day.title}
        description={day.summary}
        actions={
          <div className="flex items-center gap-2">
            {day.urgent > 0 ? <Badge tone="warn">срочных: {day.urgent}</Badge> : null}
            <Badge tone="neutral">{formatDate(day.date)}</Badge>
          </div>
        }
      />

      <div className="space-y-7">
        {parts.map((part, i) =>
          part.kind === 'md' ? (
            <article key={i} className="prose-post scroll-x">
              <Markdown remarkPlugins={[remarkGfm]}>{part.value as string}</Markdown>
            </article>
          ) : (
            <ReportBlock key={i} block={part.value as Block} />
          ),
        )}
      </div>

      <footer className="mt-12 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-5 text-sm text-muted">
        <Link href={`/projects/${project.id}`} className="text-accent underline">
          {project.title}
        </Link>
        <code className="font-mono text-xs">{day.relPath}</code>
        <span>находки — вне git</span>
      </footer>
    </div>
  )
}
