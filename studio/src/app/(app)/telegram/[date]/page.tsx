import Link from 'next/link'
import { notFound } from 'next/navigation'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { ReportBlock } from '@/components/charts'
import { Badge, PageHeader, formatDate } from '@/components/ui'
import { splitBody } from '@/lib/blocks'
import type { Block } from '@/lib/reports-model'
import { readDigest } from '@/lib/telegram'

export const dynamic = 'force-dynamic'

export default async function TelegramDigestPage({
  params,
}: {
  params: Promise<{ date: string }>
}) {
  const { date } = await params

  let digest
  try {
    digest = readDigest(date)
  } catch {
    // assertValidId бросает на мусорной дате из адресной строки.
    notFound()
  }
  if (!digest) notFound()

  const parts = splitBody(digest.body, digest.blocks)

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={digest.title}
        description={digest.summary}
        actions={<Badge tone="neutral">{formatDate(digest.date)}</Badge>}
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
        <Link href="/telegram" className="text-accent underline">
          Все сводки
        </Link>
        <code className="font-mono text-xs">{digest.relPath}</code>
        <span>выжимки — вне git</span>
      </footer>
    </div>
  )
}
