import Link from 'next/link'
import { notFound } from 'next/navigation'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { CopyPostButton } from '@/components/copy-post-button'
import { StatusSelect } from '@/components/status-select'
import { ThreadsPreview } from '@/components/threads-preview'
import { Badge, EmptyState, PageHeader, formatDate } from '@/components/ui'
import {
  PLATFORM_LABELS,
  SOURCE_LABELS,
  type Platform,
  readIdea,
  readMaterial,
  readSource,
} from '@/lib/content'
import { loadStudioConfig } from '@/lib/studio-config'

export const dynamic = 'force-dynamic'

function platformLabel(name: string): string {
  if (name === 'master') return 'Мастер-версия'
  return PLATFORM_LABELS[name as Platform] ?? name
}

export default async function IdeaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params

  let idea
  try {
    idea = readIdea(id)
  } catch {
    notFound()
  }
  if (!idea) notFound()

  const source = readSource(idea.id)
  const { author } = loadStudioConfig()
  // Пост в телегу — первым: с него начинается работа над идеей и его чаще всего копируют.
  const priority = (name: string) => (name === 'telegram' ? 0 : name === 'master' ? 1 : 2)
  const materials = [...idea.drafts, ...idea.published].sort(
    (a, b) => priority(a.name) - priority(b.name),
  )

  return (
    <>
      <PageHeader
        title={idea.title}
        description={
          <>
            {formatDate(idea.created)} · {SOURCE_LABELS[idea.source]}
            {idea.tags.length > 0 ? ` · ${idea.tags.join(', ')}` : ''}
          </>
        }
        actions={
          <>
            <StatusSelect id={idea.id} status={idea.status} />
            <Link href="/library" className="text-sm text-muted hover:text-text">
              ← В библиотеку
            </Link>
          </>
        }
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section>
          <h2 className="mb-3 font-serif text-lg font-semibold">Исходник</h2>
          {source ? (
            <div className="rounded-lg border border-border bg-surface p-5">
              <div className="prose-post text-sm whitespace-pre-wrap">{source}</div>
              <p className="mt-4 border-t border-border pt-3 text-xs text-muted">
                Не редактируется. Скиллы ставят ваши материалы выше собственного синтеза —
                исходник должен остаться таким, каким вы его надиктовали.
              </p>
            </div>
          ) : (
            <EmptyState
              title="Исходника нет"
              hint="Идея была заведена одним заголовком."
            />
          )}
        </section>

        <section>
          <h2 className="mb-3 font-serif text-lg font-semibold">Материалы</h2>
          {materials.length === 0 ? (
            <EmptyState
              title="Пока ничего не написано"
              hint="Здесь появятся мастер-версия и адаптации под площадки. Создание черновиков подключается на следующем этапе — сейчас студия показывает то, что уже есть на диске."
            />
          ) : (
            <ul className="space-y-4">
              {materials.map((material) => {
                const content = readMaterial(idea.id, material.kind, material.name)
                return (
                  <li
                    key={`${material.kind}-${material.name}`}
                    className="rounded-lg border border-border bg-surface p-5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={material.kind === 'published' ? 'ok' : 'accent'}>
                        {platformLabel(material.name)}
                      </Badge>
                      {material.kind === 'published' ? <Badge tone="ok">Опубликовано</Badge> : null}
                      <span className="text-xs text-muted">{material.chars} знаков</span>
                      <span className="ml-auto flex items-center gap-3">
                        {material.name === 'telegram' ? (
                          <CopyPostButton markdown={content.body} />
                        ) : null}
                        {material.url ? (
                          <a
                            href={material.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm text-accent underline"
                          >
                            Публикация ↗
                          </a>
                        ) : null}
                      </span>
                    </div>

                    {material.platform === 'threads' ? (
                      <ThreadsPreview body={content.body} author={author} />
                    ) : (
                      <div className="prose-post mt-4">
                        <Markdown remarkPlugins={[remarkGfm]}>{content.body}</Markdown>
                      </div>
                    )}

                    <p className="mt-4 border-t border-border pt-3 font-mono text-xs text-muted">
                      {material.relPath}
                    </p>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
    </>
  )
}
