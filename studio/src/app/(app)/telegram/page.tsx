import Link from 'next/link'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { ReportBlock } from '@/components/charts'
import { Badge, Card, EmptyState, PageHeader, formatDate } from '@/components/ui'
import type { Block } from '@/lib/reports-model'
import { loadStudioConfig } from '@/lib/studio-config'
import { digestTotals, listDigests, listRules } from '@/lib/telegram'
import { RULE_STATUS_LABELS, type RuleStatus } from '@/lib/telegram-model'

export const dynamic = 'force-dynamic'

const STATUS_TONES: Record<RuleStatus, 'ok' | 'warn' | 'neutral'> = {
  active: 'ok',
  paused: 'warn',
  proposed: 'neutral',
}

export default function TelegramPage() {
  const rules = listRules()
  const digests = listDigests()
  const totals = digestTotals(digests)
  const digestsDir = loadStudioConfig().data.telegramDigests

  const summary: Block = {
    type: 'kpi',
    items: [
      { label: 'Прогонов', value: String(totals.runs) },
      { label: 'Чатов прочитано', value: String(totals.chats) },
      { label: 'Сообщений', value: String(totals.messages) },
      {
        label: 'Последний прогон',
        value: totals.lastRun ? formatDate(totals.lastRun) : '—',
        note: totals.failed ? `ошибок за всё время: ${totals.failed}` : undefined,
      },
    ],
  }

  return (
    <div className="space-y-10">
      <PageHeader
        title="Telegram"
        description="Правила обращения с личным Telegram-аккаунтом, статистика их работы и ежедневные выжимки того, что было проглочено автоматически."
      />

      <section className="space-y-4">
        <h2 className="font-serif text-lg font-medium">Правила</h2>
        {rules.length === 0 ? (
          <EmptyState
            title="Правил пока нет"
            hint="Правило появляется здесь само, как только в content/telegram/rules/ ложится markdown-файл. Пересборка не нужна."
          />
        ) : (
          <ul className="space-y-3">
            {rules.map((rule) => (
              <li key={rule.id}>
                <Card>
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <span className="font-serif text-lg font-medium">{rule.title}</span>
                    <Badge tone={STATUS_TONES[rule.status]}>{RULE_STATUS_LABELS[rule.status]}</Badge>
                  </div>
                  <dl className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-[auto_1fr]">
                    {rule.scope ? (
                      <>
                        <dt className="text-muted">К чему</dt>
                        <dd>{rule.scope}</dd>
                      </>
                    ) : null}
                    {rule.action ? (
                      <>
                        <dt className="text-muted">Что делает</dt>
                        <dd>{rule.action}</dd>
                      </>
                    ) : null}
                    {rule.since ? (
                      <>
                        <dt className="text-muted">С какого дня</dt>
                        <dd>{formatDate(rule.since)}</dd>
                      </>
                    ) : null}
                  </dl>
                  {rule.body ? (
                    <article className="prose-post scroll-x mt-3 text-sm">
                      <Markdown remarkPlugins={[remarkGfm]}>{rule.body}</Markdown>
                    </article>
                  ) : null}
                  <code className="mt-3 block font-mono text-xs text-muted">{rule.relPath}</code>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      {digests.length > 0 ? (
        <section className="space-y-4">
          <h2 className="font-serif text-lg font-medium">Как правило отработало</h2>
          <ReportBlock block={summary} />
        </section>
      ) : null}

      <section className="space-y-4">
        <h2 className="font-serif text-lg font-medium">Дневные сводки</h2>
        {digests.length === 0 ? (
          <EmptyState
            title="Сводок пока нет"
            hint={
              <>
                Их кладёт внешний сборщик в <code>{digestsDir}/&lt;дата&gt;.md</code> — мимо git:
                в выжимках содержание личной переписки. Папка задаётся в{' '}
                <code>studio.json</code>.
              </>
            }
          />
        ) : (
          <ul className="space-y-3">
            {digests.map((digest) => (
              <li key={digest.date}>
                <Link
                  href={`/telegram/${digest.date}`}
                  className="block rounded-lg border border-border bg-surface p-4 transition-colors hover:border-accent"
                >
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="font-serif text-lg font-medium">{digest.title}</span>
                    <span className="text-sm text-muted">{formatDate(digest.date)}</span>
                  </div>
                  {digest.summary ? (
                    <p className="mt-1.5 text-sm text-muted">{digest.summary}</p>
                  ) : null}
                  {digest.failed > 0 ? (
                    <div className="mt-3">
                      <Badge tone="warn">ошибок: {digest.failed}</Badge>
                    </div>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
