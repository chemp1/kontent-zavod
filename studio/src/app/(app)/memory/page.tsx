import Link from 'next/link'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Badge, EmptyState, PageHeader } from '@/components/ui'
import { readLayers, readProposals } from '@/lib/memory'
import { loadSkillMap, type ResolvedNode } from '@/lib/skill-map'

export const dynamic = 'force-dynamic'

/** Узел канона голоса с карты скилла. Карты может не быть — тогда и ссылки нет. */
function findCanon(): ResolvedNode | null {
  try {
    return loadSkillMap().nodes.find((node) => node.type === 'canon') ?? null
  } catch {
    return null
  }
}

export default function MemoryPage() {
  const layers = readLayers()
  const proposals = readProposals()
  const pending = proposals.filter((proposal) => proposal.status === 'pending')
  const canon = findCanon()

  return (
    <>
      <PageHeader
        title="Память"
        description="Что система знает об авторе и его текстах. Уровни разделены намеренно: случайная фраза из черновика не должна весить столько же, сколько подтверждённое правило."
        actions={
          pending.length > 0 ? (
            <Badge tone="warn">{pending.length} на подтверждении</Badge>
          ) : null
        }
      />

      <section className="mb-10">
        <h2 className="mb-3 font-serif text-lg font-semibold">Предложения системы</h2>
        {proposals.length === 0 ? (
          <EmptyState
            title="Пока нечего подтверждать"
            hint="Предложения появятся, когда накопится история правок: система сравнит черновики с опубликованными версиями и найдёт повторяющиеся исправления. Ни одно из них не попадёт в скилл без вашей кнопки."
          />
        ) : (
          <ul className="space-y-3">
            {proposals.map((proposal) => (
              <li
                key={proposal.id}
                className="rounded-lg border border-border bg-surface p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    tone={
                      proposal.status === 'accepted'
                        ? 'ok'
                        : proposal.status === 'rejected'
                          ? 'neutral'
                          : 'warn'
                    }
                  >
                    {proposal.status === 'accepted'
                      ? 'Принято'
                      : proposal.status === 'rejected'
                        ? 'Отклонено'
                        : 'Ждёт решения'}
                  </Badge>
                  <span className="font-medium">{proposal.title}</span>
                  <code className="ml-auto font-mono text-xs text-muted">
                    → {proposal.target}
                  </code>
                </div>
                <div className="prose-post mt-3 text-sm">
                  <Markdown remarkPlugins={[remarkGfm]}>{proposal.body}</Markdown>
                </div>
                {proposal.evidence.length > 0 ? (
                  <p className="mt-3 text-xs text-muted">
                    Основано на: {proposal.evidence.join(', ')}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-6">
        <h2 className="font-serif text-lg font-semibold">Уровни памяти</h2>
        {layers.map((layer) => (
          <article key={layer.file} className="rounded-lg border border-border bg-surface p-5">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="font-medium">{layer.title}</h3>
              <code className="font-mono text-xs text-muted">{layer.relPath}</code>
            </div>
            <p className="mt-1 text-sm text-muted">{layer.description}</p>
            {layer.body ? (
              <div className="prose-post mt-4 text-sm">
                <Markdown remarkPlugins={[remarkGfm]}>{layer.body}</Markdown>
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted">
                Пока пусто. Заполняется по мере работы — вручную или через подтверждённые
                предложения.
              </p>
            )}
          </article>
        ))}
      </section>

      {canon ? (
        <p className="mt-8 text-sm text-muted">
          Канон голоса живёт отдельно — в{' '}
          <Link href={`/skill/${canon.id}`} className="text-accent underline">
            {canon.label}
          </Link>
          . Память дополняет его, но не заменяет.
        </p>
      ) : null}
    </>
  )
}
