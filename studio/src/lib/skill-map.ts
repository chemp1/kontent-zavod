import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { isCommittable } from './git'
import { REPO_ROOT, SKILL_MAP_FILE, resolveInside } from './paths'

export type NodeType = 'canon' | 'skill' | 'reference' | 'register' | 'corpus' | 'script' | 'doc' | 'manifest'
/** Идентификатор группы. Набор задаёт манифест, а не код, поэтому просто строка. */
export type NodeGroup = string

/** Координаты центра блока на холсте. Задаются руками; без них узел раскладывается сам. */
export interface NodeLayout {
  x: number
  y: number
}

export interface SkillNode {
  id: string
  type: NodeType
  group: NodeGroup
  label: string
  path: string
  summary: string
  layout?: NodeLayout
}

export interface SkillEdge {
  from: string
  to: string
  kind: string
  step?: number
  label?: string
}

export interface SkillGroup {
  id: string
  label: string
}

/** Свободная подпись на холсте — заголовок над ручной композицией. */
export interface MapCaption {
  x: number
  y: number
  text: string
}

export interface MapCanvas {
  width: number
  height: number
}

/**
 * Апстрим — другая копия тех же файлов (например, репозиторий методологии),
 * с которой этот скилл разошёлся бы после правки здесь. По префиксам путей
 * студия понимает, у каких узлов есть близнец, и предупреждает перед сохранением.
 */
export interface MapUpstream {
  label: string
  prefixes: string[]
}

/**
 * Манифест `content/skill-map.json`. Версия 2 добавила раскладку и всё, что
 * раньше жило в коде под конкретного автора: группы с подписями, подписи на
 * холсте, папки, которые карта обязана описывать целиком, и апстрим. Все новые
 * поля необязательные — манифест первой версии читается как есть.
 */
export interface SkillMap {
  version: number
  note?: string
  canvas?: MapCanvas
  groups?: SkillGroup[]
  captions?: MapCaption[]
  coveredDirs?: string[]
  upstream?: MapUpstream
  nodes: SkillNode[]
  edges: SkillEdge[]
}

/** Узел плюс то, что видно только с диска. */
export interface ResolvedNode extends SkillNode {
  exists: boolean
  lines: number
  bytes: number
  /** Можно ли править тело файла из интерфейса. */
  editable: boolean
  /**
   * У файла есть близнец в апстриме (см. `manifest.upstream`), и правка здесь
   * разводит копии. Показываем предупреждение перед сохранением.
   */
  upstreamTwin: boolean
}

export type IssueLevel = 'error' | 'warning'

export interface MapIssue {
  level: IssueLevel
  message: string
  nodeId?: string
  path?: string
}

/**
 * `missing` — файла нет, карта пустая; `invalid` — файл есть, но не читается,
 * причина лежит в `issues`. Оба состояния штатные: страница показывает их,
 * а не падает.
 */
export type MapStatus = 'ok' | 'missing' | 'invalid'

export interface ResolvedSkillMap {
  status: MapStatus
  version: number
  note?: string
  /** Группы из манифеста плюс те, что встретились только в узлах (подпись = id). */
  groups: SkillGroup[]
  captions: MapCaption[]
  canvas: MapCanvas
  upstream?: MapUpstream
  nodes: ResolvedNode[]
  edges: SkillEdge[]
  issues: MapIssue[]
}

export const DEFAULT_CANVAS: MapCanvas = { width: 1200, height: 830 }

const COVERED_EXTENSIONS = new Set(['.md', '.py', '.yaml', '.yml'])

/**
 * Файлы конфигурации студии из редактора не правятся, даже если попали на карту
 * и лежат в коммитимой папке: `studio.json` задаёт, что редактору можно, а
 * `skill-map.json` — что он показывает. Расширять их из самого редактора нельзя.
 */
const CONFIG_FILES = new Set(['content/studio.json', 'content/skill-map.json'])

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined
}

/** Относительный путь внутри корня: не абсолютный, не через `..`, не диск Windows. */
function relativeInsideRoot(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null
  const normalized = path.posix.normalize(value.trim().split('\\').join('/')).replace(/\/$/, '')
  if (
    normalized === '.' ||
    normalized === '..' ||
    normalized.startsWith('../') ||
    normalized.startsWith('/') ||
    /^[a-z]:/i.test(normalized)
  ) {
    return null
  }
  return normalized
}

function readLayout(value: unknown): NodeLayout | undefined {
  if (!isRecord(value) || !isFiniteNumber(value.x) || !isFiniteNumber(value.y)) return undefined
  return { x: value.x, y: value.y }
}

function readNode(value: unknown, index: number): SkillNode {
  if (!isRecord(value)) throw new Error(`nodes[${index}]: ожидался объект`)
  const id = optionalString(value.id)
  const relPath = optionalString(value.path)
  if (!id) throw new Error(`nodes[${index}]: у узла нет id`)
  if (!relPath) throw new Error(`nodes[${index}] (${id}): у узла нет path`)
  return {
    id,
    type: (optionalString(value.type) ?? 'reference') as NodeType,
    group: optionalString(value.group) ?? 'other',
    label: optionalString(value.label) ?? id,
    path: relPath,
    summary: typeof value.summary === 'string' ? value.summary : '',
    layout: readLayout(value.layout),
  }
}

function readEdge(value: unknown, index: number): SkillEdge {
  if (!isRecord(value)) throw new Error(`edges[${index}]: ожидался объект`)
  const from = optionalString(value.from)
  const to = optionalString(value.to)
  if (!from || !to) throw new Error(`edges[${index}]: у ребра должны быть from и to`)
  return {
    from,
    to,
    kind: optionalString(value.kind) ?? 'conditional',
    step: isFiniteNumber(value.step) ? value.step : undefined,
    label: optionalString(value.label),
  }
}

/**
 * Приводит сырой JSON к `SkillMap`. Структурные ошибки (нет узлов, узел без пути)
 * бросают — такой манифест показывать нечем. Необязательные поля с мусором
 * просто отбрасываются: карта без подписи лучше, чем без карты.
 */
function normalizeManifest(raw: unknown): SkillMap {
  if (!isRecord(raw)) throw new Error('ожидался JSON-объект')
  if (!Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) {
    throw new Error('ожидались поля nodes и edges')
  }

  const groups = Array.isArray(raw.groups)
    ? raw.groups.flatMap((entry): SkillGroup[] => {
        if (!isRecord(entry)) return []
        const id = optionalString(entry.id)
        return id ? [{ id, label: optionalString(entry.label) ?? id }] : []
      })
    : undefined

  const captions = Array.isArray(raw.captions)
    ? raw.captions.flatMap((entry): MapCaption[] => {
        if (!isRecord(entry) || !isFiniteNumber(entry.x) || !isFiniteNumber(entry.y)) return []
        const text = optionalString(entry.text)
        return text ? [{ x: entry.x, y: entry.y, text }] : []
      })
    : undefined

  const coveredDirs = Array.isArray(raw.coveredDirs)
    ? raw.coveredDirs.flatMap((entry) => {
        const dir = relativeInsideRoot(entry)
        return dir ? [dir] : []
      })
    : undefined

  let upstream: MapUpstream | undefined
  if (isRecord(raw.upstream)) {
    const label = optionalString(raw.upstream.label)
    const prefixes = Array.isArray(raw.upstream.prefixes)
      ? raw.upstream.prefixes.filter((entry): entry is string => typeof entry === 'string' && entry.trim() !== '')
      : []
    if (label) upstream = { label, prefixes }
  }

  let canvas: MapCanvas | undefined
  if (isRecord(raw.canvas) && isFiniteNumber(raw.canvas.width) && isFiniteNumber(raw.canvas.height)) {
    if (raw.canvas.width > 0 && raw.canvas.height > 0) {
      canvas = { width: raw.canvas.width, height: raw.canvas.height }
    }
  }

  return {
    version: isFiniteNumber(raw.version) ? raw.version : 1,
    note: optionalString(raw.note),
    canvas,
    groups,
    captions,
    coveredDirs,
    upstream,
    nodes: raw.nodes.map(readNode),
    edges: raw.edges.map(readEdge),
  }
}

export interface ManifestReadResult {
  status: MapStatus
  manifest?: SkillMap
  error?: string
}

export function readManifest(): ManifestReadResult {
  let raw: string
  try {
    raw = fs.readFileSync(SKILL_MAP_FILE, 'utf8')
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return { status: 'missing' }
    return { status: 'invalid', error: error instanceof Error ? error.message : String(error) }
  }
  try {
    return { status: 'ok', manifest: normalizeManifest(JSON.parse(raw)) }
  } catch (error) {
    return { status: 'invalid', error: error instanceof Error ? error.message : String(error) }
  }
}

function walk(dir: string): string[] {
  const abs = resolveInside(REPO_ROOT, dir)
  if (!fs.existsSync(abs)) return []
  const out: string[] = []
  for (const entry of fs.readdirSync(abs, { withFileTypes: true, recursive: true }) as fs.Dirent[]) {
    if (!entry.isFile()) continue
    const parent = (entry as unknown as { parentPath?: string; path?: string }).parentPath
      ?? (entry as unknown as { path: string }).path
    const full = path.join(parent, entry.name)
    out.push(path.relative(REPO_ROOT, full).split(path.sep).join('/'))
  }
  return out
}

/**
 * Вытаскивает относительные markdown-ссылки вида [текст](references/foo.md).
 * Внешние ссылки и якоря игнорируются.
 */
function relativeLinks(markdown: string, fromRelPath: string): string[] {
  const dir = path.posix.dirname(fromRelPath)
  const links: string[] = []
  const pattern = /\[[^\]]*\]\(([^)]+)\)/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(markdown)) !== null) {
    const target = match[1].trim()
    if (/^[a-z]+:/i.test(target) || target.startsWith('#') || target.startsWith('/')) continue
    links.push(path.posix.normalize(path.posix.join(dir, target)))
  }
  return links
}

/** Группы из манифеста в его порядке, затем те, что есть только у узлов. */
function resolveGroups(manifest: SkillMap): SkillGroup[] {
  const groups = [...(manifest.groups ?? [])]
  const known = new Set(groups.map((group) => group.id))
  for (const node of manifest.nodes) {
    if (known.has(node.group)) continue
    known.add(node.group)
    groups.push({ id: node.group, label: node.group })
  }
  return groups
}

function emptyMap(status: MapStatus, issues: MapIssue[] = []): ResolvedSkillMap {
  return {
    status,
    version: 0,
    groups: [],
    captions: [],
    canvas: DEFAULT_CANVAS,
    nodes: [],
    edges: [],
    issues,
  }
}

export function loadSkillMap(): ResolvedSkillMap {
  const read = readManifest()
  if (read.status === 'missing') return emptyMap('missing')
  if (read.status === 'invalid' || !read.manifest) {
    return emptyMap('invalid', [
      { level: 'error', message: `content/skill-map.json не читается: ${read.error ?? 'неизвестная ошибка'}` },
    ])
  }

  const manifest = read.manifest
  const issues: MapIssue[] = []
  const declaredPaths = new Set(manifest.nodes.map((node) => node.path))
  const nodeIds = new Set<string>()
  const upstreamPrefixes = manifest.upstream?.prefixes ?? []

  for (const node of manifest.nodes) {
    if (nodeIds.has(node.id)) {
      issues.push({ level: 'error', nodeId: node.id, message: `Узел объявлен дважды: ${node.id}` })
    }
    nodeIds.add(node.id)
  }

  const nodes: ResolvedNode[] = manifest.nodes.map((node) => {
    let exists = false
    let lines = 0
    let bytes = 0
    try {
      const abs = resolveInside(REPO_ROOT, node.path)
      if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
        exists = true
        const content = fs.readFileSync(abs, 'utf8')
        bytes = Buffer.byteLength(content)
        // Считаем как wc -l: завершающий перевод строки не создаёт лишнюю строку.
        lines = content ? content.replace(/\n$/, '').split('\n').length : 0
      }
    } catch {
      exists = false
    }
    if (!exists) {
      issues.push({
        level: 'error',
        nodeId: node.id,
        path: node.path,
        message: `Файл объявлен на карте, но его нет на диске: ${node.path}`,
      })
    }
    const normalizedPath = path.posix.normalize(node.path)
    return {
      ...node,
      exists,
      lines,
      bytes,
      editable:
        exists && isCommittable(node.path) && node.type !== 'corpus' && !CONFIG_FILES.has(normalizedPath),
      upstreamTwin: upstreamPrefixes.some((prefix) => node.path.startsWith(prefix)),
    }
  })

  // Рёбра должны соединять существующие узлы.
  for (const edge of manifest.edges) {
    if (!nodeIds.has(edge.from)) {
      issues.push({ level: 'error', message: `Ребро ссылается на неизвестный узел: ${edge.from}` })
    }
    if (!nodeIds.has(edge.to)) {
      issues.push({ level: 'error', message: `Ребро ссылается на неизвестный узел: ${edge.to}` })
    }
  }

  // Файл появился в скилле, но на карте его нет — самое частое расхождение.
  for (const dir of manifest.coveredDirs ?? []) {
    let files: string[]
    try {
      files = walk(dir)
    } catch {
      issues.push({ level: 'error', path: dir, message: `coveredDirs: папка выходит за пределы корня: ${dir}` })
      continue
    }
    for (const relPath of files) {
      if (!COVERED_EXTENSIONS.has(path.extname(relPath))) continue
      if (!declaredPaths.has(relPath)) {
        issues.push({
          level: 'warning',
          path: relPath,
          message: `Файл есть в скилле, но не описан на карте: ${relPath}`,
        })
      }
    }
  }

  // Ссылки внутри SKILL.md должны быть представлены рёбрами.
  for (const node of nodes) {
    if (node.type !== 'skill' || !node.exists) continue
    const abs = resolveInside(REPO_ROOT, node.path)
    const links = relativeLinks(fs.readFileSync(abs, 'utf8'), node.path)
    for (const target of links) {
      const targetNode = manifest.nodes.find((candidate) => candidate.path === target)
      if (!targetNode) {
        issues.push({
          level: 'warning',
          nodeId: node.id,
          path: target,
          message: `${node.label} ссылается на файл, которого нет на карте: ${target}`,
        })
        continue
      }
      const hasEdge = manifest.edges.some(
        (edge) => edge.from === node.id && edge.to === targetNode.id,
      )
      if (!hasEdge) {
        issues.push({
          level: 'warning',
          nodeId: node.id,
          path: target,
          message: `${node.label} читает ${targetNode.label}, но ребра между ними на карте нет`,
        })
      }
    }
  }

  return {
    status: 'ok',
    version: manifest.version,
    note: manifest.note,
    groups: resolveGroups(manifest),
    captions: manifest.captions ?? [],
    canvas: manifest.canvas ?? DEFAULT_CANVAS,
    upstream: manifest.upstream,
    nodes,
    edges: manifest.edges,
    issues,
  }
}

/** Узел по id — для страницы просмотра файла. */
export function findNode(id: string): ResolvedNode | null {
  return loadSkillMap().nodes.find((node) => node.id === id) ?? null
}

/**
 * Тело файла узла. Frontmatter из интерфейса не правится, поэтому отдаём
 * содержимое целиком и целиком же принимаем обратно.
 */
export function readNodeFile(node: ResolvedNode): string {
  const abs = resolveInside(REPO_ROOT, node.path)
  return fs.readFileSync(abs, 'utf8')
}

/**
 * Отпечаток того, что лежит на диске сейчас.
 *
 * Редактор получает его вместе с текстом и присылает обратно при сохранении.
 * Если к этому моменту файл изменила другая сессия Claude или вторая вкладка,
 * отпечатки разойдутся, и правку можно отклонить, а не затереть молча. Файлы
 * скиллов здесь правятся из нескольких мест одновременно — это норма работы,
 * а не редкий случай.
 */
export function nodeFileHash(node: ResolvedNode): string {
  return createHash('sha256').update(readNodeFile(node)).digest('hex').slice(0, 16)
}

export function writeNodeFile(node: ResolvedNode, content: string): void {
  const abs = resolveInside(REPO_ROOT, node.path)
  if (!fs.existsSync(abs)) throw new Error(`Файл не найден: ${node.path}`)
  fs.writeFileSync(abs, content.endsWith('\n') ? content : `${content}\n`, 'utf8')
}
