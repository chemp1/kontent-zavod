import fs from 'node:fs'
import path from 'node:path'

import { REPO_ROOT, STUDIO_CONFIG_FILE } from './paths'

/**
 * Всё, что в студии зависит от конкретного автора и его мастерской, лежит не
 * в коде, а в `content/studio.json`: имя и ник для превью, заголовок, список
 * папок, которые студии разрешено коммитить, и где внешние сборщики оставляют
 * данные вне git. Код при этом один и тот же у любого, кто поднял студию над
 * своей папкой с текстами.
 *
 * Файл необязателен: без него работают дефолты, и об этом пишется в лог один раз.
 */
export interface StudioAuthor {
  /** Как обращаться к автору в интерфейсе. */
  name: string
  /** Ник в превью площадок (Threads показывает его вместо имени). */
  handle: string
  /** Буква на аватаре в превью. */
  initial: string
}

export interface StudioDataDirs {
  /** Дневные сводки по личному Telegram: `<дата>.md` + `<дата>.data.json`. Относительно корня. */
  telegramDigests: string
  /** Находки по проектам наблюдения: `<проект>/<дата>.md`. Относительно корня. */
  projectFindings: string
}

export interface StudioConfig {
  version: number
  title: string
  author: StudioAuthor
  git: {
    /** Префиксы путей относительно корня, которые студия имеет право коммитить. */
    committable: string[]
  }
  /**
   * Папки вне git, которые студия только читает. Сюда пишут внешние сборщики,
   * и раскладка у каждого своя — поэтому это настройка, а не константа.
   */
  data: StudioDataDirs
}

export const DEFAULT_CONFIG: StudioConfig = {
  version: 1,
  title: 'Контентная студия',
  author: { name: 'Автор', handle: 'author', initial: 'А' },
  git: { committable: ['content/'] },
  data: {
    telegramDigests: '.data/telegram/digests',
    projectFindings: '.data/telegram/projects',
  },
}

/** Относительный путь внутри корня: не абсолютный, не через `..`, не диск Windows. */
function isInsideRoot(normalized: string): boolean {
  return !(
    normalized === '.' ||
    normalized === '..' ||
    normalized.startsWith('../') ||
    normalized.startsWith('/') ||
    /^[a-z]:/i.test(normalized)
  )
}

function normalizeRelative(entry: string): string {
  return path.posix.normalize(entry.trim().split('\\').join('/'))
}

/**
 * Приводит список коммитимых префиксов к виду, с которым работает `isCommittable()`:
 * относительный нормализованный путь без `..`, с завершающим `/`. `content/` есть
 * всегда — без неё студия не смогла бы сохранить ни одной идеи. Мусор отбрасывается
 * с предупреждением, а не роняет загрузку: конфиг правят руками.
 */
export function normalizeCommittable(input: unknown): string[] {
  const out = new Set<string>(['content/'])
  if (!Array.isArray(input)) return [...out]

  for (const entry of input) {
    if (typeof entry !== 'string' || !entry.trim()) {
      console.warn(`[studio] studio.json: пропускаю запись в git.committable: ${JSON.stringify(entry)}`)
      continue
    }
    const normalized = normalizeRelative(entry)
    if (!isInsideRoot(normalized)) {
      console.warn(`[studio] studio.json: префикс должен быть относительным и без «..»: ${entry}`)
      continue
    }
    out.add(normalized.endsWith('/') ? normalized : `${normalized}/`)
  }
  return [...out]
}

function relativeDir(value: unknown, key: string, fallback: string): string {
  if (typeof value !== 'string' || !value.trim()) return fallback
  const normalized = normalizeRelative(value)
  if (!isInsideRoot(normalized)) {
    console.warn(`[studio] studio.json: data.${key} должен быть относительным и без «..»: ${value}`)
    return fallback
  }
  return normalized.replace(/\/$/, '')
}

function str(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function section(data: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = data[key]
  return (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
}

function fromRaw(raw: unknown): StudioConfig {
  const data = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const author = section(data, 'author')
  const git = section(data, 'git')
  const dirs = section(data, 'data')
  const name = str(author.name, DEFAULT_CONFIG.author.name)
  return {
    version: typeof data.version === 'number' ? data.version : DEFAULT_CONFIG.version,
    title: str(data.title, DEFAULT_CONFIG.title),
    author: {
      name,
      handle: str(author.handle, DEFAULT_CONFIG.author.handle),
      // Без явной буквы берём первую от имени: «Анна» → «А».
      initial: str(author.initial, name.slice(0, 1).toUpperCase() || DEFAULT_CONFIG.author.initial),
    },
    git: { committable: normalizeCommittable(git.committable) },
    data: {
      telegramDigests: relativeDir(dirs.telegramDigests, 'telegramDigests', DEFAULT_CONFIG.data.telegramDigests),
      projectFindings: relativeDir(dirs.projectFindings, 'projectFindings', DEFAULT_CONFIG.data.projectFindings),
    },
  }
}

let cached: { mtimeMs: number; config: StudioConfig } | null = null
let warnedMissing = false

/**
 * Синхронно, потому что зовётся из серверных компонентов и из `isCommittable()`,
 * который стоит на пути каждого коммита. Кэш по mtime: правка файла подхватывается
 * следующим запросом, без перезапуска.
 */
export function loadStudioConfig(): StudioConfig {
  let mtimeMs: number
  try {
    mtimeMs = fs.statSync(STUDIO_CONFIG_FILE).mtimeMs
  } catch {
    if (!warnedMissing) {
      console.warn(`[studio] ${STUDIO_CONFIG_FILE} не найден — работаю с дефолтами (npm run init создаст его)`)
      warnedMissing = true
    }
    cached = null
    return DEFAULT_CONFIG
  }
  warnedMissing = false

  if (cached && cached.mtimeMs === mtimeMs) return cached.config

  let config: StudioConfig
  try {
    config = fromRaw(JSON.parse(fs.readFileSync(STUDIO_CONFIG_FILE, 'utf8')))
  } catch (error) {
    console.warn(
      `[studio] ${STUDIO_CONFIG_FILE} не читается, беру дефолты: ${error instanceof Error ? error.message : error}`,
    )
    config = DEFAULT_CONFIG
  }
  cached = { mtimeMs, config }
  return config
}

/**
 * Абсолютный путь к папке данных вне git. Значение уже проверено при загрузке,
 * так что за корень оно не выйдет; `commitPaths()` такие пути всё равно не пропустит —
 * они не начинаются с `content/`.
 */
export function dataRoot(key: keyof StudioDataDirs): string {
  return path.resolve(REPO_ROOT, loadStudioConfig().data[key])
}
