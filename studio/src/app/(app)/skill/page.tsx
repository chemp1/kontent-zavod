import Link from 'next/link'

import { SkillGraph } from '@/components/skill-graph'
import { Badge, EmptyState, PageHeader, formatBytes } from '@/components/ui'
import { loadSkillMap } from '@/lib/skill-map'

export const dynamic = 'force-dynamic'

export default function SkillPage() {
  const map = loadSkillMap()

  if (map.status === 'missing') {
    return (
      <>
        <PageHeader
          title="Карта скилла"
          description="Файлы скилла голоса и связи между ними: что из чего выведено и кто что читает."
        />
        <EmptyState
          title="Карты скилла пока нет"
          hint={
            <>
              Карта описывается в <code>content/skill-map.json</code>: узлы — файлы скилла,
              рёбра — кто что читает. Стартовый манифест положит <code>npm run init</code>{' '}
              в папке <code>studio/</code>; пути в нём подставьте под свою раскладку.
            </>
          }
        />
      </>
    )
  }

  const errors = map.issues.filter((issue) => issue.level === 'error')
  const warnings = map.issues.filter((issue) => issue.level === 'warning')

  if (map.status === 'invalid') {
    return (
      <>
        <PageHeader
          title="Карта скилла"
          description="Файлы скилла голоса и связи между ними: что из чего выведено и кто что читает."
          actions={<Badge tone="danger">манифест не читается</Badge>}
        />
        <div className="rounded-lg border border-danger bg-danger-soft p-4">
          <p className="text-sm font-medium">Манифест карты не читается</p>
          <ul className="mt-2 space-y-1 text-sm">
            {errors.map((issue, index) => (
              <li key={index}>
                <span className="text-danger">✗</span> {issue.message}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">
            Поправьте <code>content/skill-map.json</code> руками и обновите страницу: студия
            перечитывает манифест на каждый запрос.
          </p>
        </div>
      </>
    )
  }

  const totalLines = map.nodes.reduce((sum, node) => sum + node.lines, 0)

  return (
    <>
      <PageHeader
        title="Карта скилла"
        description={`${map.nodes.length} файлов, ${totalLines.toLocaleString('ru-RU')} строк. Канон в центре, вокруг — то, что из него выведено и что его применяет.`}
        actions={
          map.issues.length === 0 ? (
            <Badge tone="ok">Карта совпадает с диском</Badge>
          ) : (
            <Badge tone={errors.length > 0 ? 'danger' : 'warn'}>
              {errors.length > 0
                ? `${errors.length} ошибок`
                : `${warnings.length} расхождений`}
            </Badge>
          )
        }
      />

      {map.issues.length > 0 ? (
        <div
          className={`mb-6 rounded-lg border p-4 ${
            errors.length > 0
              ? 'border-danger bg-danger-soft'
              : 'border-warn bg-warn-soft'
          }`}
        >
          <p className="text-sm font-medium">Карта разошлась с файлами</p>
          <ul className="mt-2 space-y-1 text-sm">
            {map.issues.map((issue, index) => (
              <li key={index}>
                <span className={issue.level === 'error' ? 'text-danger' : 'text-warn'}>
                  {issue.level === 'error' ? '✗' : '!'}
                </span>{' '}
                {issue.message}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">
            Структура графа правится руками в <code>content/skill-map.json</code> — из
            интерфейса меняется только тело файлов.
          </p>
        </div>
      ) : null}

      {map.nodes.length > 0 ? (
        <SkillGraph
          nodes={map.nodes}
          edges={map.edges}
          groups={map.groups}
          captions={map.captions}
          canvas={map.canvas}
        />
      ) : (
        <EmptyState
          title="На карте нет ни одного узла"
          hint={
            <>
              Манифест прочитан, но список <code>nodes</code> пуст. Опишите файлы скилла в{' '}
              <code>content/skill-map.json</code> — образец лежит в{' '}
              <code>studio/templates/content/</code>.
            </>
          }
        />
      )}

      <div className="mt-10 space-y-8">
        {map.groups.map((group) => {
          const nodes = map.nodes.filter((node) => node.group === group.id)
          if (nodes.length === 0) return null
          return (
            <section key={group.id}>
              <h2 className="mb-3 font-serif text-lg font-semibold">{group.label}</h2>
              <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface">
                {nodes.map((node) => (
                  <li key={node.id}>
                    <Link
                      href={`/skill/${node.id}`}
                      className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 transition-colors hover:bg-surface-2"
                    >
                      <span className="font-medium">{node.label}</span>
                      <code className="font-mono text-xs text-muted">{node.path}</code>
                      <span className="ml-auto text-xs text-muted">
                        {node.exists ? `${node.lines} строк · ${formatBytes(node.bytes)}` : 'нет файла'}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>
    </>
  )
}
