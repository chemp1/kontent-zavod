import path from 'node:path'

/**
 * Корень — папка, где лежат `content/` и файлы скилла. Приложение живёт в её
 * подпапке `studio/`, поэтому по умолчанию поднимаемся на уровень выше от cwd.
 * Переопределяется `STUDIO_ROOT`, чтобы студию можно было запустить откуда угодно.
 */
export const REPO_ROOT = process.env.STUDIO_ROOT
  ? path.resolve(process.env.STUDIO_ROOT)
  : path.resolve(process.cwd(), '..')

export const CONTENT_ROOT = path.join(REPO_ROOT, 'content')
/** Настройки студии: автор, заголовок, что можно коммитить. См. lib/studio-config.ts. */
export const STUDIO_CONFIG_FILE = path.join(CONTENT_ROOT, 'studio.json')
export const IDEAS_ROOT = path.join(CONTENT_ROOT, 'ideas')
export const MEMORY_ROOT = path.join(CONTENT_ROOT, 'memory')
export const REPORTS_ROOT = path.join(CONTENT_ROOT, 'reports')
export const SKILL_MAP_FILE = path.join(CONTENT_ROOT, 'skill-map.json')

/** Контент-план: сетка ритма и слоты календаря. */
export const PLAN_ROOT = path.join(CONTENT_ROOT, 'plan')
export const PLAN_SLOTS_ROOT = path.join(PLAN_ROOT, 'slots')
/** Идеи-кандидаты из звонков — их кладёт внешний майнер, решает человек. */
export const PLAN_CANDIDATES_ROOT = path.join(PLAN_ROOT, 'candidates')
export const PLAN_RHYTHM_FILE = path.join(PLAN_ROOT, 'rhythm.md')

/** Карточки трендов от внешнего сборщика и список его источников. */
export const TRENDS_ROOT = path.join(CONTENT_ROOT, 'trends')
export const TRENDS_SOURCES_FILE = path.join(TRENDS_ROOT, 'sources.md')

/** Правила работы в Telegram — обычный контент, живут в git. */
export const TELEGRAM_RULES_ROOT = path.join(CONTENT_ROOT, 'telegram', 'rules')

/** Описания проектов — тем наблюдения за Telegram. Обычный контент, в git. */
export const PROJECTS_ROOT = path.join(CONTENT_ROOT, 'telegram', 'projects')

/*
 * Сводки по переписке и находки по проектам живут вне git — в выжимках содержание
 * личной и чужих переписок. Где именно, решает `studio.json` (`data.*`), см.
 * `dataRoot()` в lib/studio-config.ts: раскладка у внешних сборщиков своя.
 */

/**
 * Единственный способ собрать путь из недоверенного сегмента.
 *
 * Любой id, пришедший из URL или из тела запроса, проходит здесь: результат
 * обязан остаться внутри `base`, иначе бросаем. Это защита не от ошибки, а от
 * `../../` в адресной строке — приложение читает и пишет файлы репозитория.
 */
export function resolveInside(base: string, ...segments: string[]): string {
  const target = path.resolve(base, ...segments)
  const normalizedBase = path.resolve(base)
  if (target !== normalizedBase && !target.startsWith(normalizedBase + path.sep)) {
    throw new Error(`Путь выходит за пределы ${normalizedBase}: ${target}`)
  }
  return target
}

/** Путь относительно корня репозитория — в таком виде их понимает git. */
export function toRepoRelative(absolutePath: string): string {
  return path.relative(REPO_ROOT, absolutePath).split(path.sep).join('/')
}

/**
 * Идентификатор идеи — это имя папки, поэтому набор символов ограничен строго:
 * латиница, цифры, дефис. Кириллица транслитерируется на входе (см. slugify).
 */
const ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,119}$/

export function assertValidId(id: string): string {
  if (!ID_PATTERN.test(id)) {
    throw new Error(`Недопустимый идентификатор: ${JSON.stringify(id)}`)
  }
  return id
}
