import Link from 'next/link'
import { notFound } from 'next/navigation'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { ReportBlock } from '@/components/charts'
import { Badge, PageHeader, formatDate } from '@/components/ui'
import { splitBody } from '@/lib/blocks'
import { readReport } from '@/lib/reports'
import type { Block } from '@/lib/reports-model'

export const dynamic = 'force-dynamic'

export default async function ReportPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params

  let report
  try {
    report = readReport(slug)
  } catch {
    // assertValidId бросает на мусорном слаге из адресной строки.
    notFound()
  }
  if (!report) notFound()

  const parts = splitBody(report.body, report.blocks)

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={report.title}
        description={report.summary}
        actions={report.date ? <Badge tone="neutral">{formatDate(report.date)}</Badge> : null}
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
        <Link href="/reports" className="text-accent underline">
          Все отчёты
        </Link>
        <code className="font-mono text-xs">{report.relPath}</code>
      </footer>
    </div>
  )
}
