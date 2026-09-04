'use client'

import { useRouter } from 'next/navigation'
import { useMemo, useState } from 'react'

import type {
  MapCanvas,
  MapCaption,
  ResolvedNode,
  SkillEdge,
  SkillGroup,
  SkillNode,
} from '@/lib/skill-map'

/*
 * Раскладка живёт в манифесте, а не в коде: граф маленький, его структура известна
 * автору, и силовая раскладка только мешала бы — она каждый раз рисует по-новому
 * и разносит связанные узлы. Узел с `layout` встаёт ровно туда, куда его поставили.
 *
 * Узлы без координат раскладываются сами: по группам в колонки, в порядке групп
 * из манифеста, под самым нижним ручным узлом (или с верха холста, если ручных
 * нет). Над каждой такой колонкой — подпись группы. Так свежий манифест без единой
 * координаты выглядит осмысленно, а не кучей.
 */

const BOX_WIDTH = 190
const BOX_HEIGHT = 44
const CANON_WIDTH = 300
const CANON_HEIGHT = 78

/** Отступ между блоками в автоколонке и между подписью и первым блоком. */
const AUTO_GAP = 14
const AUTO_TOP = 80
const AUTO_LABEL_OFFSET = 22
const MIN_COLUMN_WIDTH = 220

type Point = { x: number; y: number }

export interface GraphLayout {
  positions: Map<string, Point>
  /** Подписи над автоколонками — в том же стиле, что и ручные подписи. */
  labels: MapCaption[]
  width: number
  height: number
}

function boxHeight(node: SkillNode): number {
  return node.type === 'canon' ? CANON_HEIGHT : BOX_HEIGHT
}

/**
 * Чистая функция: узлы + группы + холст → координаты центров, подписи над
 * автоколонками и итоговый размер холста (растёт, если узлы не влезли).
 */
export function computePositions(
  nodes: SkillNode[],
  groups: SkillGroup[],
  canvas: MapCanvas,
): GraphLayout {
  const positions = new Map<string, Point>()
  const auto: SkillNode[] = []
  let maxManualY: number | null = null

  for (const node of nodes) {
    if (node.layout) {
      positions.set(node.id, node.layout)
      maxManualY = Math.max(maxManualY ?? -Infinity, node.layout.y)
    } else {
      auto.push(node)
    }
  }

  const labels: MapCaption[] = []
  let columnsWidth = 0

  if (auto.length > 0) {
    const autoTop = maxManualY === null ? AUTO_TOP : maxManualY + 80

    // Порядок колонок — порядок групп в манифесте; группы, которых там нет,
    // встают в конец в порядке появления.
    const order = groups.map((group) => group.id)
    for (const node of auto) {
      if (!order.includes(node.group)) order.push(node.group)
    }
    const columns = order
      .map((id) => ({
        label: groups.find((group) => group.id === id)?.label ?? id,
        nodes: auto.filter((node) => node.group === id),
      }))
      .filter((column) => column.nodes.length > 0)

    // Канон шире обычного блока: колонка с ним должна вмещать его половину плюс
    // половину соседнего блока, иначе они наедут друг на друга.
    const minWidth = auto.some((node) => node.type === 'canon')
      ? Math.max(MIN_COLUMN_WIDTH, (CANON_WIDTH + BOX_WIDTH) / 2 + 20)
      : MIN_COLUMN_WIDTH
    const colWidth = Math.max(minWidth, canvas.width / columns.length)
    columnsWidth = colWidth * columns.length

    columns.forEach((column, index) => {
      const x = colWidth * (index + 0.5)
      labels.push({ x, y: autoTop - AUTO_LABEL_OFFSET, text: column.label })
      let cursor = autoTop
      for (const node of column.nodes) {
        const height = boxHeight(node)
        positions.set(node.id, { x, y: cursor + height / 2 })
        cursor += height + AUTO_GAP
      }
    })
  }

  let bottom = 0
  for (const node of nodes) {
    const position = positions.get(node.id)
    if (position) bottom = Math.max(bottom, position.y + boxHeight(node) / 2)
  }

  return {
    positions,
    labels,
    width: Math.max(canvas.width, columnsWidth),
    height: Math.max(canvas.height, bottom + 20),
  }
}

const EDGE_STYLES: Record<string, { stroke: string; dash?: string; width: number }> = {
  always: { stroke: 'var(--accent)', width: 2 },
  derives: { stroke: 'var(--muted)', dash: '2 3', width: 1.5 },
  deep: { stroke: 'var(--accent)', dash: '5 4', width: 1.5 },
  platform: { stroke: 'var(--accent)', dash: '5 4', width: 1.5 },
  conditional: { stroke: 'var(--border)', dash: '3 4', width: 1.5 },
  verify: { stroke: 'var(--ok)', dash: '6 3', width: 1.5 },
  subagent: { stroke: 'var(--warn)', width: 1.5 },
  handoff: { stroke: 'var(--accent)', width: 2.5 },
  step: { stroke: 'var(--accent)', width: 2 },
  precedence: { stroke: 'var(--danger)', dash: '1 4', width: 1.5 },
}

const TYPE_STYLES: Record<string, { fill: string; stroke: string; text: string; weight: number }> = {
  canon: { fill: 'var(--accent-soft)', stroke: 'var(--accent)', text: 'var(--accent)', weight: 600 },
  skill: { fill: 'var(--surface)', stroke: 'var(--accent)', text: 'var(--text)', weight: 600 },
  reference: { fill: 'var(--surface)', stroke: 'var(--border)', text: 'var(--text)', weight: 400 },
  register: { fill: 'var(--surface)', stroke: 'var(--muted)', text: 'var(--text)', weight: 400 },
  corpus: { fill: 'var(--ok-soft)', stroke: 'var(--ok)', text: 'var(--text)', weight: 400 },
  script: { fill: 'var(--warn-soft)', stroke: 'var(--warn)', text: 'var(--text)', weight: 400 },
  doc: { fill: 'var(--surface-2)', stroke: 'var(--border)', text: 'var(--muted)', weight: 400 },
  manifest: { fill: 'var(--surface-2)', stroke: 'var(--border)', text: 'var(--muted)', weight: 400 },
}

const LEGEND: { kind: string; label: string }[] = [
  { kind: 'always', label: 'читает всегда' },
  { kind: 'platform', label: 'по площадке' },
  { kind: 'conditional', label: 'по задаче' },
  { kind: 'verify', label: 'сверяется' },
  { kind: 'subagent', label: 'субагент' },
  { kind: 'handoff', label: 'передача' },
  { kind: 'derives', label: 'выведено из' },
  { kind: 'precedence', label: 'кто главнее' },
]

const CAPTION_FONT_SIZE = 11
const CAPTION_LETTER_SPACING = 1.4

/** Грубая оценка ширины строки — SVG сам текст не переносит и не обрезает. */
function truncate(label: string, maxWidth: number, fontSize: number, letterSpacing = 0): string {
  const perChar = fontSize * 0.55 + letterSpacing
  const maxChars = Math.floor(maxWidth / perChar)
  return label.length <= maxChars ? label : `${label.slice(0, maxChars - 1)}…`
}

function Caption({ caption, maxWidth }: { caption: MapCaption; maxWidth?: number }) {
  return (
    <text
      x={caption.x}
      y={caption.y}
      textAnchor="middle"
      fontSize={CAPTION_FONT_SIZE}
      letterSpacing={CAPTION_LETTER_SPACING}
      fill="var(--muted)"
      style={{ textTransform: 'uppercase' }}
    >
      {maxWidth
        ? truncate(caption.text, maxWidth, CAPTION_FONT_SIZE, CAPTION_LETTER_SPACING)
        : caption.text}
    </text>
  )
}

export function SkillGraph({
  nodes,
  edges,
  groups,
  captions,
  canvas,
}: {
  nodes: ResolvedNode[]
  edges: SkillEdge[]
  groups: SkillGroup[]
  captions: MapCaption[]
  canvas: MapCanvas
}) {
  const router = useRouter()
  const [hovered, setHovered] = useState<string | null>(null)

  const layout = useMemo(() => computePositions(nodes, groups, canvas), [nodes, groups, canvas])
  const { positions } = layout
  const columnWidth = layout.labels.length > 0 ? layout.width / layout.labels.length : undefined

  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes])
  const visibleEdges = edges.filter((edge) => positions.has(edge.from) && positions.has(edge.to))

  /** Узлы, связанные с наведённым, — они остаются яркими вместе с ним. */
  const related = useMemo(() => {
    if (!hovered) return null
    const set = new Set<string>([hovered])
    for (const edge of visibleEdges) {
      if (edge.from === hovered) set.add(edge.to)
      if (edge.to === hovered) set.add(edge.from)
    }
    return set
  }, [hovered, visibleEdges])

  const hoveredNode = hovered ? nodeById.get(hovered) : null

  return (
    <div>
      <div className="scroll-x rounded-lg border border-border bg-surface-2">
        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          className="h-auto w-full min-w-[960px]"
          role="img"
          aria-label="Карта скилла: файлы и связи между ними"
        >
          {captions.map((caption, index) => (
            <Caption key={`caption-${index}`} caption={caption} />
          ))}
          {layout.labels.map((caption, index) => (
            <Caption
              key={`column-${index}`}
              caption={caption}
              maxWidth={columnWidth ? columnWidth - 20 : undefined}
            />
          ))}

          <g>
            {visibleEdges.map((edge, index) => {
              const from = positions.get(edge.from)!
              const to = positions.get(edge.to)!
              const style = EDGE_STYLES[edge.kind] ?? EDGE_STYLES.conditional
              const active = hovered === edge.from || hovered === edge.to
              const dimmed = hovered !== null && !active
              return (
                <line
                  key={`${edge.from}-${edge.to}-${index}`}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={style.stroke}
                  strokeWidth={active ? style.width + 1 : style.width}
                  strokeDasharray={style.dash}
                  opacity={dimmed ? 0.08 : active ? 1 : 0.4}
                />
              )
            })}
          </g>

          <g>
            {nodes.map((node) => {
              const position = positions.get(node.id)!
              const style = TYPE_STYLES[node.type] ?? TYPE_STYLES.reference
              const isCanon = node.type === 'canon'
              const width = isCanon ? CANON_WIDTH : BOX_WIDTH
              const height = isCanon ? CANON_HEIGHT : BOX_HEIGHT
              const fontSize = isCanon ? 16 : 12.5
              const dimmed = related !== null && !related.has(node.id)

              return (
                <g
                  key={node.id}
                  transform={`translate(${position.x - width / 2} ${position.y - height / 2})`}
                  className="cursor-pointer"
                  opacity={dimmed ? 0.25 : 1}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => router.push(`/skill/${node.id}`)}
                  role="link"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') router.push(`/skill/${node.id}`)
                  }}
                >
                  <rect
                    width={width}
                    height={height}
                    rx={isCanon ? 12 : 8}
                    fill={style.fill}
                    stroke={node.exists ? style.stroke : 'var(--danger)'}
                    strokeWidth={hovered === node.id ? 2.5 : isCanon ? 2 : 1.25}
                    strokeDasharray={node.exists ? undefined : '4 3'}
                  />

                  {isCanon ? (
                    <text
                      x={width / 2}
                      y={22}
                      textAnchor="middle"
                      fontSize={10}
                      letterSpacing={1.4}
                      fill="var(--accent)"
                      style={{ textTransform: 'uppercase' }}
                    >
                      канон голоса
                    </text>
                  ) : null}

                  <text
                    x={width / 2}
                    y={isCanon ? 46 : height / 2 - 3}
                    textAnchor="middle"
                    fontSize={fontSize}
                    fontWeight={style.weight}
                    fill={style.text}
                  >
                    {truncate(node.label, width - 18, fontSize)}
                  </text>

                  <text
                    x={width / 2}
                    y={isCanon ? 64 : height / 2 + 13}
                    textAnchor="middle"
                    fontSize={10}
                    fill="var(--muted)"
                  >
                    {node.exists ? `${node.lines} строк` : 'файла нет'}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
        {LEGEND.map((item) => {
          const style = EDGE_STYLES[item.kind]
          return (
            <span key={item.kind} className="flex items-center gap-2">
              <svg width="26" height="8" aria-hidden="true">
                <line
                  x1="0"
                  y1="4"
                  x2="26"
                  y2="4"
                  stroke={style.stroke}
                  strokeWidth={style.width}
                  strokeDasharray={style.dash}
                />
              </svg>
              {item.label}
            </span>
          )
        })}
      </div>

      <div className="mt-4 min-h-[4.5rem] rounded-lg border border-border bg-surface p-4">
        {hoveredNode ? (
          <>
            <p className="font-medium">{hoveredNode.label}</p>
            <p className="mt-1 text-sm text-muted">{hoveredNode.summary}</p>
          </>
        ) : (
          <p className="text-sm text-muted">
            Наведите на блок, чтобы прочитать, за что он отвечает и что с ним связано.
            Клик открывает файл с историей изменений.
          </p>
        )}
      </div>
    </div>
  )
}
