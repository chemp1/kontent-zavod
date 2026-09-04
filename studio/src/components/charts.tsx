import type { BarsBlock, Block, DumbbellBlock, KpiBlock, StackBlock } from '@/lib/reports-model'

/**
 * Графики отчётов. Серверные компоненты, без клиентского JS и без библиотек.
 *
 * Общие правила, одинаковые во всех формах:
 * - марки тонкие, скруглён только конец данных, у основания угол прямой;
 * - цвет несут марки, текст всегда в текстовых токенах;
 * - подписи выборочные, а не число у каждой точки;
 * - соседние заливки разделяет зазор цветом поверхности, а не обводка;
 * - у каждого графика есть таблица-двойник: значение никогда не доступно
 *   только через наведение мыши.
 */

const STACK_COLORS = [
  'var(--chart-4)',
  'var(--chart-3)',
  'var(--chart-2)',
  'var(--chart-1)',
]

function fmt(value: number, unit?: string): string {
  const num =
    Math.abs(value) >= 10000
      ? `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}K`
      : value.toLocaleString('ru-RU')
  return unit ? `${num}${unit === '%' ? '' : ' '}${unit}` : num
}

function Frame({
  title,
  hint,
  sample,
  children,
  table,
}: {
  title: string
  hint?: string
  sample?: number
  children: React.ReactNode
  table: React.ReactNode
}) {
  return (
    <figure className="rounded-lg border border-border bg-surface p-5">
      <figcaption className="mb-5">
        <h3 className="font-medium">{title}</h3>
        {hint ? <p className="mt-1 text-sm text-muted">{hint}</p> : null}
        {sample ? (
          <p className="mt-1 text-xs text-muted">
            Выборка: {sample.toLocaleString('ru-RU')}
          </p>
        ) : null}
      </figcaption>

      {children}

      <details className="mt-5 border-t border-border pt-3">
        <summary className="cursor-pointer text-xs text-muted">Таблицей</summary>
        <div className="scroll-x mt-3">{table}</div>
      </details>
    </figure>
  )
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs text-muted">
          {head.map((cell) => (
            <th key={cell} className="py-1.5 pr-4 font-normal">
              {cell}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="tabular-nums">
        {rows.map((row) => (
          <tr key={String(row[0])} className="border-b border-border/60 last:border-0">
            {row.map((cell, i) => (
              <td key={i} className={`py-1.5 pr-4 ${i === 0 ? 'tabular-nums-off' : ''}`}>
                {typeof cell === 'number' ? cell.toLocaleString('ru-RU') : cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Плитки чисел. Одно число — не график: у него нет ни осей, ни сравнения. */
function Kpi({ block }: { block: KpiBlock }) {
  return (
    <section>
      {block.title ? (
        <h3 className="mb-3 font-medium">{block.title}</h3>
      ) : null}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {block.items.map((item) => (
          <div key={item.label} className="rounded-lg border border-border bg-surface p-4">
            <div className="text-sm text-muted">{item.label}</div>
            {/* Пропорциональные цифры: tabular-nums на крупном числе
                растягивает его и выглядит рыхло. */}
            <div className="mt-1 text-2xl font-semibold">{item.value}</div>
            {item.note ? <div className="mt-1 text-xs text-muted">{item.note}</div> : null}
          </div>
        ))}
      </div>
    </section>
  )
}

/** Величины по категориям: один ряд, один цвет, значение у конца полосы. */
function Bars({ block }: { block: BarsBlock }) {
  const max = Math.max(...block.items.map((i) => Math.abs(i.value)), 1)

  return (
    <Frame
      title={block.title}
      hint={block.hint}
      sample={block.sample}
      table={
        <Table
          head={['Категория', block.unit || 'Значение', 'Примечание']}
          rows={block.items.map((i) => [i.label, i.value, i.note || ''])}
        />
      }
    >
      <div className="space-y-2.5">
        {block.items.map((item) => (
          <div key={item.label} className="flex items-center gap-3">
            <div className="w-36 shrink-0 truncate text-sm sm:w-44" title={item.label}>
              {item.label}
            </div>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <div
                className="h-2.5 shrink-0 rounded-r-[4px]"
                style={{
                  width: `${Math.max((Math.abs(item.value) / max) * 100, 1)}%`,
                  background: 'var(--chart-3)',
                }}
              />
              <span className="shrink-0 font-mono text-xs text-muted">
                {fmt(item.value, block.unit)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Frame>
  )
}

/**
 * Две группы по одному набору признаков. Гантель вместо парных столбиков:
 * читателю нужен разрыв между группами, а разрыв — это расстояние, и глазу
 * проще мерить его отрезком, чем сравнивать длины двух соседних полос.
 */
function Dumbbell({ block }: { block: DumbbellBlock }) {
  const max = Math.max(...block.items.flatMap((i) => [i.a, i.b]), 1)
  const pos = (v: number) => `${(v / max) * 100}%`

  return (
    <Frame
      title={block.title}
      hint={block.hint}
      sample={block.sample}
      table={
        <Table
          head={['Признак', block.legend.a, block.legend.b, 'Разрыв']}
          rows={block.items.map((i) => [
            i.label,
            fmt(i.a, block.unit),
            fmt(i.b, block.unit),
            `${i.a - i.b > 0 ? '+' : ''}${fmt(i.a - i.b, block.unit)}`,
          ])}
        />
      }
    >
      {/* Два ряда — легенда обязательна: опознание не должно держаться
          на одном только цвете. */}
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: 'var(--chart-4)' }}
          />
          {block.legend.a}
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: 'var(--chart-1)' }}
          />
          {block.legend.b}
        </span>
      </div>

      <div className="space-y-3.5">
        {block.items.map((item) => (
          <div key={item.label} className="flex items-center gap-3">
            <div className="w-36 shrink-0 truncate text-sm sm:w-44" title={item.label}>
              {item.label}
            </div>
            <div className="relative h-4 min-w-0 flex-1">
              {/* Ось: сплошная волосяная линия на шаг от поверхности. */}
              <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
              <div
                className="absolute top-1/2 h-0.5 -translate-y-1/2"
                style={{
                  left: pos(Math.min(item.a, item.b)),
                  width: pos(Math.abs(item.a - item.b)),
                  background: 'var(--chart-2)',
                }}
              />
              {[
                { v: item.b, color: 'var(--chart-1)' },
                { v: item.a, color: 'var(--chart-4)' },
              ].map(({ v, color }, i) => (
                <span
                  key={i}
                  className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{
                    left: pos(v),
                    background: color,
                    // Кольцо цветом поверхности: точки остаются различимы
                    // там, где накладываются друг на друга.
                    boxShadow: '0 0 0 2px var(--surface)',
                  }}
                />
              ))}
            </div>
            <div className="w-14 shrink-0 text-right font-mono text-xs text-muted">
              {fmt(item.a, block.unit)}
            </div>
          </div>
        ))}
      </div>
    </Frame>
  )
}

/** Доли целого одной полосой. Сегменты разделяет зазор цветом поверхности. */
function Stack({ block }: { block: StackBlock }) {
  const total = block.items.reduce((sum, i) => sum + i.value, 0) || 1

  return (
    <Frame
      title={block.title}
      hint={block.hint}
      sample={block.sample}
      table={
        <Table
          head={['Часть', 'Доля']}
          rows={block.items.map((i) => [i.label, `${Math.round((i.value / total) * 100)}%`])}
        />
      }
    >
      <div className="flex h-3.5 w-full gap-0.5 overflow-hidden">
        {block.items.map((item, i) => (
          <div
            key={item.label}
            className="h-full first:rounded-l-[4px] last:rounded-r-[4px]"
            style={{
              width: `${(item.value / total) * 100}%`,
              background: STACK_COLORS[i % STACK_COLORS.length],
            }}
          />
        ))}
      </div>

      {/* Подписи вынесены под полосу: внутрь узкого сегмента текст не влезает,
          а обрезанная подпись хуже её отсутствия. */}
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {block.items.map((item, i) => (
          <span key={item.label} className="flex items-center gap-1.5 text-sm">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: STACK_COLORS[i % STACK_COLORS.length] }}
            />
            <span className="text-muted">{item.label}</span>
            <span className="font-mono text-xs">
              {Math.round((item.value / total) * 100)}%
            </span>
          </span>
        ))}
      </div>
    </Frame>
  )
}

export function ReportBlock({ block }: { block: Block }) {
  switch (block.type) {
    case 'kpi':
      return <Kpi block={block} />
    case 'bars':
      return <Bars block={block} />
    case 'dumbbell':
      return <Dumbbell block={block} />
    case 'stack':
      return <Stack block={block} />
    default:
      return null
  }
}
