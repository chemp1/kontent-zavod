import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

import { PLATFORM_LIMITS, isPlatform, type Idea, type Platform } from './content-model'
import { listIdeas, today } from './content'
import { parseFile, str } from './frontmatter'
import { PLAN_RHYTHM_FILE, PLAN_SLOTS_ROOT, assertValidId, resolveInside, toRepoRelative } from './paths'
import {
  WEEKDAYS,
  isWeekday,
  type DayPlan,
  type PlannedSlot,
  type PlatformLoad,
  type Rhythm,
  type RhythmRow,
  type Rubric,
  type Slot,
  type SlotState,
  type Weekday,
  type WeekPlan,
} from './plan-model'

export * from './plan-model'

/**
 * Контент-план: слоты календаря плюс сетка ритма.
 *
 * Модуль умышленно не хранит состояние слота. Всё, что можно вывести из идеи
 * (есть ли черновик, вышел ли пост, какая ссылка), выводится здесь при чтении —
 * см. `stateOf()`. Файл слота отвечает только на вопрос «что и когда».
 */

// ---------------------------------------------------------------- даты

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/
/** Ключ рубрики и имя материала — те же ограничения, что у имён файлов. */
const NAME_PATTERN = /^[a-z][a-z0-9-]{0,39}$/

/**
 * Считаем даты в UTC-полночи: арифметика по местному времени в дни перехода
 * на летнее время даёт 23 или 25 часов, и неделя разъезжается на день.
 */
function toUtc(date: string): Date {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}

function fromUtc(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export function addDays(date: string, days: number): string {
  const shifted = toUtc(date)
  shifted.setUTCDate(shifted.getUTCDate() + days)
  return fromUtc(shifted)
}

export function weekdayOf(date: string): Weekday {
  // getUTCDay(): 0 — воскресенье, а неделя у нас начинается с понедельника.
  return WEEKDAYS[(toUtc(date).getUTCDay() + 6) % 7]
}

/** Понедельник недели, в которую попадает дата. */
export function weekStart(date: string): string {
  const index = WEEKDAYS.indexOf(weekdayOf(date))
  return addDays(date, -index)
}

export function isValidDate(value: string): boolean {
  return DATE_PATTERN.test(value) && fromUtc(toUtc(value)) === value
}

// ---------------------------------------------------------------- ритм

const EMPTY_RHYTHM: Rhythm = { rubrics: [], rows: [], body: '', relPath: '', broken: false }

function parseRubrics(value: unknown): Rubric[] {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      const item = (entry ?? {}) as Record<string, unknown>
      return {
        key: str(item, 'key'),
        label: str(item, 'label'),
        hint: str(item, 'hint'),
      }
    })
    .filter((rubric) => rubric.key !== '')
}

function parseRows(value: unknown): RhythmRow[] {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      const item = (entry ?? {}) as Record<string, unknown>
      const platform = str(item, 'platform')
      const days = Array.isArray(item.days) ? item.days.filter(isWeekday) : []
      if (!isPlatform(platform) || days.length === 0) return null
      return {
        platform,
        time: str(item, 'time', '12:00'),
        rubric: str(item, 'rubric'),
        days,
      }
    })
    .filter((row): row is RhythmRow => row !== null)
}

export function readRhythm(): Rhythm {
  if (!fs.existsSync(PLAN_RHYTHM_FILE)) return EMPTY_RHYTHM
  const { data, content } = parseFile(PLAN_RHYTHM_FILE)
  const rows = parseRows(data.grid)
  return {
    rubrics: parseRubrics(data.rubrics),
    rows,
    body: content.trim(),
    relPath: toRepoRelative(PLAN_RHYTHM_FILE),
    broken: rows.length === 0 && Object.keys(data).length === 0,
  }
}

// ---------------------------------------------------------------- слоты

function parseSlot(id: string, abs: string): Slot | null {
  const { data, content } = parseFile(abs)
  const platform = str(data, 'platform')
  const date = str(data, 'date')
  if (!isPlatform(platform) || !isValidDate(date)) return null

  return {
    id,
    date,
    time: str(data, 'time', '12:00'),
    platform,
    rubric: str(data, 'rubric'),
    ideaId: str(data, 'idea'),
    material: str(data, 'material'),
    note: content.trim(),
    relPath: toRepoRelative(abs),
  }
}

export function listSlots(): Slot[] {
  if (!fs.existsSync(PLAN_SLOTS_ROOT)) return []
  return fs
    .readdirSync(PLAN_SLOTS_ROOT)
    .filter((file) => file.endsWith('.md'))
    .map((file) => parseSlot(file.replace(/\.md$/, ''), path.join(PLAN_SLOTS_ROOT, file)))
    .filter((slot): slot is Slot => slot !== null)
    .sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time))
}

export function readSlot(id: string): Slot | null {
  assertValidId(id)
  const abs = resolveInside(PLAN_SLOTS_ROOT, `${id}.md`)
  if (!fs.existsSync(abs)) return null
  return parseSlot(id, abs)
}

// ---------------------------------------------------------------- состояние

/**
 * Состояние слота выводится из идеи, а не хранится: файл слота говорит «когда
 * и о чём», идея — «написано ли». Один факт в одном месте.
 */
function describe(slot: Omit<Slot, 'id' | 'relPath'>, idea: Idea | undefined) {
  const name = slot.material || slot.platform
  const published = idea?.published.find((material) => material.name === name)
  const draft = idea?.drafts.find((material) => material.name === name)
  const material = published ?? draft

  let state: SlotState = 'empty'
  if (published) state = 'published'
  else if (draft) state = 'draft'
  else if (idea) state = 'needs-draft'

  return {
    state,
    ideaTitle: idea?.title ?? '',
    chars: material?.chars ?? 0,
    limit: PLATFORM_LIMITS[slot.platform] ?? null,
    url: published?.url ?? '',
  }
}

function plan(slot: Slot, ideas: Map<string, Idea>): PlannedSlot {
  return { ...slot, ghost: false, ...describe(slot, ideas.get(slot.ideaId)) }
}

/** Слот, которого на диске нет: его предлагает ритм. Заводится по клику. */
function ghost(date: string, row: RhythmRow): PlannedSlot {
  return {
    id: null,
    relPath: null,
    date,
    time: row.time,
    platform: row.platform,
    rubric: row.rubric,
    ideaId: '',
    material: '',
    note: '',
    ghost: true,
    state: 'empty',
    ideaTitle: '',
    chars: 0,
    limit: PLATFORM_LIMITS[row.platform] ?? null,
    url: '',
  }
}

function ideaIndex(): Map<string, Idea> {
  return new Map(listIdeas().map((idea) => [idea.id, idea]))
}

/**
 * День календаря: заведённые слоты плюс призраки ритма там, где на эту пару
 * «площадка + время» слота ещё нет.
 */
function buildDay(date: string, slots: Slot[], rhythm: Rhythm, ideas: Map<string, Idea>): DayPlan {
  const weekday = weekdayOf(date)
  const own = slots.filter((slot) => slot.date === date)
  const taken = new Set(own.map((slot) => `${slot.platform}@${slot.time}`))

  const ghosts = rhythm.rows
    .filter((row) => row.days.includes(weekday) && !taken.has(`${row.platform}@${row.time}`))
    .map((row) => ghost(date, row))

  const all = [...own.map((slot) => plan(slot, ideas)), ...ghosts].sort(
    (a, b) => a.time.localeCompare(b.time) || a.platform.localeCompare(b.platform),
  )

  return { date, weekday, slots: all }
}

export function buildWeek(anchor?: string): WeekPlan {
  const start = weekStart(anchor && isValidDate(anchor) ? anchor : today())
  const slots = listSlots()
  const rhythm = readRhythm()
  const ideas = ideaIndex()

  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i)).map((date) =>
    buildDay(date, slots, rhythm, ideas),
  )

  const load = new Map<Platform, PlatformLoad>()
  const bump = (platform: Platform, patch: Partial<PlatformLoad>) => {
    const current = load.get(platform) ?? { platform, planned: 0, rhythm: 0, ready: 0 }
    load.set(platform, {
      platform,
      planned: current.planned + (patch.planned ?? 0),
      rhythm: current.rhythm + (patch.rhythm ?? 0),
      ready: current.ready + (patch.ready ?? 0),
    })
  }

  for (const day of days) {
    for (const slot of day.slots) {
      if (slot.ghost) {
        bump(slot.platform, { rhythm: 1 })
        continue
      }
      bump(slot.platform, { planned: 1, rhythm: 1 })
      if (slot.state === 'draft' || slot.state === 'published') bump(slot.platform, { ready: 1 })
    }
  }

  return {
    start,
    previous: addDays(start, -7),
    next: addDays(start, 7),
    days,
    load: [...load.values()].sort((a, b) => b.rhythm - a.rhythm || a.platform.localeCompare(b.platform)),
    rubrics: rhythm.rubrics,
    rhythmBroken: rhythm.broken,
  }
}

export function buildDayPlan(date: string): DayPlan {
  return buildDay(date, listSlots(), readRhythm(), ideaIndex())
}

/**
 * Очередь: идеи, которые ещё никуда не поставлены. Опубликованные и отклонённые
 * в очереди не нужны — они уже прожили свою жизнь.
 */
export function unscheduledIdeas(): Idea[] {
  const planned = new Set(listSlots().map((slot) => slot.ideaId).filter(Boolean))
  return listIdeas().filter(
    (idea) =>
      !planned.has(idea.id) &&
      idea.status !== 'published' &&
      idea.status !== 'rejected' &&
      idea.status !== 'parked',
  )
}

// ---------------------------------------------------------------- запись

export interface SlotInput {
  date: string
  time: string
  platform: string
  rubric?: string
  ideaId?: string
  material?: string
  note?: string
}

/** Слот плюс пути, которые нужно закоммитить (при переносе их два). */
export interface SlotWrite {
  slot: Slot
  touched: string[]
}

/** Тело запроса из браузера — приводим к строкам; всё остальное проверит `clean()`. */
export function slotInputFrom(payload: Record<string, unknown>): SlotInput {
  const text = (key: string) => (typeof payload[key] === 'string' ? (payload[key] as string) : '')
  return {
    date: text('date'),
    time: text('time'),
    platform: text('platform'),
    rubric: text('rubric'),
    ideaId: text('ideaId'),
    material: text('material'),
    note: text('note'),
  }
}

function clean(input: SlotInput): Omit<Slot, 'id' | 'relPath'> {
  if (!isValidDate(input.date)) throw new Error(`Недопустимая дата: ${input.date}`)
  if (!TIME_PATTERN.test(input.time)) throw new Error(`Недопустимое время: ${input.time}`)
  if (!isPlatform(input.platform)) throw new Error(`Неизвестная площадка: ${input.platform}`)

  const rubric = (input.rubric ?? '').trim()
  if (rubric && !NAME_PATTERN.test(rubric)) throw new Error(`Недопустимая рубрика: ${rubric}`)

  const material = (input.material ?? '').trim()
  if (material && !NAME_PATTERN.test(material)) throw new Error(`Недопустимый материал: ${material}`)

  const ideaId = (input.ideaId ?? '').trim()
  if (ideaId) assertValidId(ideaId)

  return {
    date: input.date,
    time: input.time,
    platform: input.platform,
    rubric,
    ideaId,
    material,
    note: (input.note ?? '').trim(),
  }
}

function write(id: string, slot: Omit<Slot, 'id' | 'relPath'>): Slot {
  assertValidId(id)
  fs.mkdirSync(PLAN_SLOTS_ROOT, { recursive: true })
  const abs = resolveInside(PLAN_SLOTS_ROOT, `${id}.md`)

  // Дата и время — в кавычках: без них YAML отдаёт дату объектом Date, а `09:00`
  // читается как шестидесятеричное число.
  const frontmatter: Record<string, unknown> = {
    date: slot.date,
    time: slot.time,
    platform: slot.platform,
  }
  if (slot.rubric) frontmatter.rubric = slot.rubric
  if (slot.ideaId) frontmatter.idea = slot.ideaId
  if (slot.material) frontmatter.material = slot.material

  fs.writeFileSync(abs, matter.stringify(slot.note ? `${slot.note}\n` : '', frontmatter), 'utf8')

  const written = parseSlot(id, abs)
  if (!written) throw new Error(`Слот ${id} не читается после записи`)
  return written
}

function freeId(date: string, platform: string): string {
  const base = `${date}-${platform}`
  let id = base
  let suffix = 2
  while (fs.existsSync(path.join(PLAN_SLOTS_ROOT, `${id}.md`))) {
    id = `${base}-${suffix++}`
  }
  return id
}

export function createSlot(input: SlotInput): SlotWrite {
  const slot = clean(input)
  const written = write(freeId(slot.date, slot.platform), slot)
  return { slot: written, touched: [written.relPath] }
}

/**
 * Правка слота. Если поменялись дата или площадка, файл переезжает: имя слота —
 * это его дата и площадка, и оставлять `2026-09-01-threads.md` с датой на неделю
 * позже значит заводить второй, врущий источник правды.
 */
export function updateSlot(id: string, input: SlotInput): SlotWrite {
  const existing = readSlot(id)
  if (!existing) throw new Error(`Слот ${id} не найден`)

  const next = clean(input)
  const moved = next.date !== existing.date || next.platform !== existing.platform
  if (!moved) {
    const written = write(id, next)
    return { slot: written, touched: [written.relPath] }
  }

  const written = write(freeId(next.date, next.platform), next)
  fs.unlinkSync(resolveInside(PLAN_SLOTS_ROOT, `${id}.md`))
  return { slot: written, touched: [written.relPath, existing.relPath] }
}

export function deleteSlot(id: string): { slot: Slot; touched: string[] } {
  const existing = readSlot(id)
  if (!existing) throw new Error(`Слот ${id} не найден`)
  fs.unlinkSync(resolveInside(PLAN_SLOTS_ROOT, `${id}.md`))
  return { slot: existing, touched: [existing.relPath] }
}
