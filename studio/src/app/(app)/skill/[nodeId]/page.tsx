import Link from 'next/link'
import { notFound } from 'next/navigation'

import { FileEditor } from '@/components/file-editor'
import { Badge, PageHeader, formatBytes } from '@/components/ui'
import { fileAtRev, fileHistory, isDirty } from '@/lib/git'
import { findNode, loadSkillMap, nodeFileHash, readNodeFile } from '@/lib/skill-map'

export const dynamic = 'force-dynamic'

export default async function SkillNodePage({
  params,
  searchParams,
}: {
  params: Promise<{ nodeId: string }>
  searchParams: Promise<{ rev?: string }>
}) {
  const { nodeId } = await params
  const { rev } = await searchParams

  const node = findNode(nodeId)
  if (!node) notFound()

  const map = loadSkillMap()
  const incoming = map.edges.filter((edge) => edge.to === node.id)
  const outgoing = map.edges.filter((edge) => edge.from === node.id)
  const labelOf = (id: string) => map.nodes.find((candidate) => candidate.id === id)?.label ?? id

  const history = await fileHistory(node.path)
  const dirty = await isDirty(node.path)

  const revContent = rev ? await fileAtRev(node.path, rev) : null
  const current = node.exists ? readNodeFile(node) : ''
  const viewingOld = Boolean(rev && revContent !== null)

  return (
    <>
      <PageHeader
        title={node.label}
        description={node.summary}
        actions={<Link href="/skill" className="text-sm text-muted hover:text-text">← К карте</Link>}
      />

      <div className="mb-6 flex flex-wrap items-center gap-2 text-sm">
        <code className="rounded bg-surface-2 px-2 py-1 font-mono text-xs">{node.path}</code>
        {node.exists ? (
          <span className="text-muted">
            {node.lines} строк · {formatBytes(node.bytes)}
          </span>
        ) : (
          <Badge tone="danger">файла нет на диске</Badge>
        )}
        {dirty ? <Badge tone="warn">есть незакоммиченные правки</Badge> : null}
        {!node.editable && node.exists ? <Badge tone="neutral">только чтение</Badge> : null}
      </div>

      {node.editable && node.upstreamTwin && map.upstream ? (
        <p className="mb-6 rounded-lg border border-warn bg-warn-soft p-3 text-sm">
          У этого файла есть близнец в апстриме <code>{map.upstream.label}</code>.
          Правка здесь разводит копии — перенести её туда придётся руками, иначе версии
          разъедутся.
        </p>
      ) : null}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          {viewingOld ? (
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <Badge tone="accent">версия {rev?.slice(0, 7)}</Badge>
                <Link href={`/skill/${node.id}`} className="text-sm text-accent underline">
                  Вернуться к текущей
                </Link>
              </div>
              <pre className="scroll-x max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface p-4 font-mono text-xs whitespace-pre-wrap">
                {revContent}
              </pre>
            </div>
          ) : node.editable ? (
            <FileEditor nodeId={node.id} initialContent={current} baseHash={nodeFileHash(node)} />
          ) : (
            <pre className="scroll-x max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface p-4 font-mono text-xs whitespace-pre-wrap">
              {current || 'Файл пуст или недоступен.'}
            </pre>
          )}
        </div>

        <aside className="space-y-7">
          <section>
            <h2 className="mb-2 text-sm font-semibold">Связи</h2>
            {outgoing.length === 0 && incoming.length === 0 ? (
              <p className="text-sm text-muted">Не связан ни с чем — вероятно, это расхождение.</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {outgoing.map((edge, index) => (
                  <li key={`out-${index}`}>
                    <span className="text-muted">→ </span>
                    <Link href={`/skill/${edge.to}`} className="text-accent underline">
                      {labelOf(edge.to)}
                    </Link>
                    {edge.label ? <span className="text-muted"> — {edge.label}</span> : null}
                  </li>
                ))}
                {incoming.map((edge, index) => (
                  <li key={`in-${index}`}>
                    <span className="text-muted">← </span>
                    <Link href={`/skill/${edge.from}`} className="text-accent underline">
                      {labelOf(edge.from)}
                    </Link>
                    {edge.label ? <span className="text-muted"> — {edge.label}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold">История</h2>
            {history.length === 0 ? (
              <p className="text-sm text-muted">Файл ещё не попадал в коммиты.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {history.map((commit) => (
                  <li key={commit.sha}>
                    <Link
                      href={`/skill/${node.id}?rev=${commit.sha}`}
                      className={`block rounded-md border p-2 transition-colors hover:border-accent ${
                        rev === commit.sha ? 'border-accent bg-accent-soft' : 'border-border'
                      }`}
                    >
                      <span className="block">{commit.subject}</span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {new Date(commit.date).toLocaleDateString('ru-RU')} · {commit.shortSha}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </>
  )
}
