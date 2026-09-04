import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

import {
  PLATFORMS,
  STATUSES,
  isSource,
  isStatus,
  type Idea,
  type Material,
  type Platform,
  type Source,
  type Status,
} from './content-model'
import { IDEAS_ROOT, assertValidId, resolveInside, toRepoRelative } from './paths'

export * from './content-model'

const TRANSLIT: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z',
  и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r',
  с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'c', ч: 'ch', ш: 'sh', щ: 'sch',
  ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
}

export function slugify(title: string): string {
  const base = title
    .toLowerCase()
    .split('')
    .map((ch) => (ch in TRANSLIT ? TRANSLIT[ch] : ch))
    .join('')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .replace(/-+$/g, '')
  return base || 'ideya'
}

/**
 * Сегодняшняя дата по часам машины, а не по UTC.
 *
 * `toISOString()` отдаёт UTC, и в Берлине идея, заведённая в 00:30, получала бы
 * вчерашнее число — в id папки, в сортировке библиотеки и в показанной дате.
 * Ночь тут рабочее время, так что это не теоретический случай.
 * Локаль `en-CA` даёт ровно `ГГГГ-ММ-ДД`.
 */
export function today(): string {
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

function platformFromName(name: string): Platform | 'master' {
  if (name === 'master') return 'master'
  return (PLATFORMS as readonly string[]).includes(name) ? (name as Platform) : 'master'
}

function readMaterials(ideaDir: string, kind: 'draft' | 'published'): Material[] {
  const dir = path.join(ideaDir, kind === 'draft' ? 'drafts' : 'published')
  if (!fs.existsSync(dir)) return []

  return fs
    .readdirSync(dir)
    .filter((file) => file.endsWith('.md'))
    .map((file) => {
      const abs = path.join(dir, file)
      const parsed = matter(fs.readFileSync(abs, 'utf8'))
      const name = file.replace(/\.md$/, '')
      const data = parsed.data as Record<string, unknown>
      return {
        name,
        platform: platformFromName(name),
        kind,
        relPath: toRepoRelative(abs),
        updated: typeof data.updated === 'string' ? data.updated : undefined,
        url: typeof data.url === 'string' ? data.url : undefined,
        from: typeof data.from === 'string' ? data.from : undefined,
        chars: parsed.content.trim().length,
      }
    })
    .sort((a, b) => {
      // Мастер-версия всегда первая — от неё растут остальные.
      if (a.name === 'master') return -1
      if (b.name === 'master') return 1
      return a.name.localeCompare(b.name)
    })
}

export function readIdea(id: string): Idea | null {
  assertValidId(id)
  const dir = resolveInside(IDEAS_ROOT, id)
  const ideaFile = path.join(dir, 'idea.md')
  if (!fs.existsSync(ideaFile)) return null

  const parsed = matter(fs.readFileSync(ideaFile, 'utf8'))
  const data = parsed.data as Record<string, unknown>

  return {
    id,
    title: typeof data.title === 'string' && data.title.trim() ? data.title : id,
    status: isStatus(data.status) ? data.status : 'idea',
    created: typeof data.created === 'string' ? data.created : today(),
    source: isSource(data.source) ? data.source : 'text',
    tags: Array.isArray(data.tags) ? data.tags.map(String) : [],
    dir,
    relDir: toRepoRelative(dir),
    hasSource: fs.existsSync(path.join(dir, 'source.md')),
    drafts: readMaterials(dir, 'draft'),
    published: readMaterials(dir, 'published'),
  }
}

export function listIdeas(): Idea[] {
  if (!fs.existsSync(IDEAS_ROOT)) return []
  return fs
    .readdirSync(IDEAS_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      try {
        return readIdea(entry.name)
      } catch {
        // Папка с недопустимым именем — показываем библиотеку без неё, а не 500.
        return null
      }
    })
    .filter((idea): idea is Idea => idea !== null)
    .sort((a, b) => b.created.localeCompare(a.created) || a.id.localeCompare(b.id))
}

export interface CreateIdeaInput {
  title: string
  source?: Source
  sourceText?: string
  tags?: string[]
}

export function createIdea(input: CreateIdeaInput): Idea {
  const title = input.title.trim()
  if (!title) throw new Error('У идеи должен быть заголовок')

  const created = today()
  const base = `${created}-${slugify(title)}`
  let id = base
  let suffix = 2
  while (fs.existsSync(path.join(IDEAS_ROOT, id))) {
    id = `${base}-${suffix++}`
  }
  assertValidId(id)

  const dir = resolveInside(IDEAS_ROOT, id)
  fs.mkdirSync(path.join(dir, 'drafts'), { recursive: true })
  fs.mkdirSync(path.join(dir, 'published'), { recursive: true })

  const frontmatter = matter.stringify('', {
    id,
    title,
    status: 'idea',
    created,
    source: input.source ?? 'text',
    tags: input.tags ?? [],
  })
  fs.writeFileSync(path.join(dir, 'idea.md'), frontmatter, 'utf8')

  const sourceText = input.sourceText?.trim()
  if (sourceText) {
    // Исходник неприкосновенен: скиллы ставят «его материалы» выше своего синтеза,
    // поэтому мы его только пишем при создании и больше не редактируем.
    fs.writeFileSync(
      path.join(dir, 'source.md'),
      matter.stringify(`${sourceText}\n`, { captured: created }),
      'utf8',
    )
  }

  const idea = readIdea(id)
  if (!idea) throw new Error(`Идея ${id} не создалась`)
  return idea
}

export function setStatus(id: string, status: Status): Idea {
  assertValidId(id)
  if (!(STATUSES as readonly string[]).includes(status)) {
    throw new Error(`Неизвестный статус: ${status}`)
  }
  const dir = resolveInside(IDEAS_ROOT, id)
  const ideaFile = path.join(dir, 'idea.md')
  if (!fs.existsSync(ideaFile)) throw new Error(`Идея ${id} не найдена`)

  const parsed = matter(fs.readFileSync(ideaFile, 'utf8'))
  fs.writeFileSync(
    ideaFile,
    matter.stringify(parsed.content, { ...parsed.data, status }),
    'utf8',
  )

  const idea = readIdea(id)
  if (!idea) throw new Error(`Идея ${id} не читается после смены статуса`)
  return idea
}

const MATERIAL_NAME = /^[a-z][a-z0-9-]{0,39}$/

export interface MaterialContent {
  frontmatter: Record<string, unknown>
  body: string
  relPath: string
  exists: boolean
}

export function readMaterial(
  id: string,
  kind: 'draft' | 'published',
  name: string,
): MaterialContent {
  assertValidId(id)
  if (!MATERIAL_NAME.test(name)) throw new Error(`Недопустимое имя материала: ${name}`)

  const dir = resolveInside(IDEAS_ROOT, id, kind === 'draft' ? 'drafts' : 'published')
  const file = resolveInside(dir, `${name}.md`)
  if (!fs.existsSync(file)) {
    return { frontmatter: {}, body: '', relPath: toRepoRelative(file), exists: false }
  }

  const parsed = matter(fs.readFileSync(file, 'utf8'))
  return {
    frontmatter: parsed.data as Record<string, unknown>,
    body: parsed.content.replace(/^\n+/, ''),
    relPath: toRepoRelative(file),
    exists: true,
  }
}

export function writeMaterial(
  id: string,
  kind: 'draft' | 'published',
  name: string,
  body: string,
  extraFrontmatter: Record<string, unknown> = {},
): MaterialContent {
  assertValidId(id)
  if (!MATERIAL_NAME.test(name)) throw new Error(`Недопустимое имя материала: ${name}`)

  const dir = resolveInside(IDEAS_ROOT, id, kind === 'draft' ? 'drafts' : 'published')
  fs.mkdirSync(dir, { recursive: true })
  const file = resolveInside(dir, `${name}.md`)

  const existing = fs.existsSync(file)
    ? (matter(fs.readFileSync(file, 'utf8')).data as Record<string, unknown>)
    : {}

  const frontmatter: Record<string, unknown> = {
    ...existing,
    ...extraFrontmatter,
    updated: today(),
  }
  if (name !== 'master' && !frontmatter.platform) frontmatter.platform = name
  if (name !== 'master' && !frontmatter.from) frontmatter.from = 'drafts/master.md'

  fs.writeFileSync(file, matter.stringify(`${body.trim()}\n`, frontmatter), 'utf8')
  return readMaterial(id, kind, name)
}

export function readSource(id: string): string | null {
  assertValidId(id)
  const file = resolveInside(IDEAS_ROOT, id, 'source.md')
  if (!fs.existsSync(file)) return null
  return matter(fs.readFileSync(file, 'utf8')).content.trim()
}
