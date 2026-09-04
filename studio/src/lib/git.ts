import { execFile } from 'node:child_process'
import path from 'node:path'
import { promisify } from 'node:util'

import { REPO_ROOT } from './paths'
import { loadStudioConfig } from './studio-config'

const run = promisify(execFile)

/**
 * Приложение коммитит только то, что само же и правит. Список префиксов живёт
 * в `content/studio.json` (`git.committable`); `content/` в нём есть всегда.
 * Всё остальное — корпус, документация, `CLAUDE.md`, чужие репозитории —
 * недоступно, даже если путь дойдёт сюда по ошибке.
 *
 * Большие выгрузки-доказательства (например, корпус постов) в список сознательно
 * не включают: их не редактируют в текстовом поле браузера.
 */
export function committablePrefixes(): string[] {
  return loadStudioConfig().git.committable
}

export function isCommittable(relPath: string): boolean {
  if (!relPath || path.isAbsolute(relPath)) return false

  // Сравнивать префикс до нормализации нельзя: `.claude/skills/../../CLAUDE.md`
  // проходит startsWith, а указывает на файл вне списка. `resolveInside()` такое
  // не ловит — путь остаётся внутри репозитория, просто не там, где разрешено.
  const normalized = path.posix.normalize(relPath.split(path.sep).join('/'))
  if (normalized === '..' || normalized.startsWith('../') || normalized.startsWith('/')) {
    return false
  }

  return committablePrefixes().some((prefix) => normalized.startsWith(prefix))
}

export interface Commit {
  sha: string
  shortSha: string
  date: string
  author: string
  subject: string
}

async function git(args: string[]): Promise<string> {
  const { stdout } = await run('git', args, {
    cwd: REPO_ROOT,
    maxBuffer: 32 * 1024 * 1024,
  })
  return stdout
}

type ExecError = NodeJS.ErrnoException & { stderr?: string; killed?: boolean }

/**
 * Переводит типовые отказы git на человеческий: это то, что увидит пользователь
 * рядом с кнопкой «Сохранить». Сырой stderr уходит в лог — там его и искать.
 */
function explainGitError(error: unknown): string {
  const err = (error ?? {}) as ExecError
  const stderr = typeof err.stderr === 'string' ? err.stderr.trim() : ''
  if (stderr) console.error(`[studio] git: ${stderr}`)

  if (err.code === 'ENOENT') return 'git не установлен'
  if (err.killed) return 'git не ответил вовремя'
  if (/Author identity unknown|Please tell me who you are/i.test(stderr)) {
    return `задайте git config user.name и user.email в ${REPO_ROOT}`
  }
  if (/index\.lock/i.test(stderr)) return 'git занят другой сессией'
  if (/not a git repository/i.test(stderr)) {
    return `${REPO_ROOT} не git-репозиторий: выполните git init`
  }
  const firstLine = stderr.split('\n')[0]
  return firstLine ? `git: ${firstLine}` : 'git вернул ошибку, подробности в логе студии'
}

export interface GitStatus {
  available: boolean
  reason?: string
}

/**
 * Есть ли вообще git, в который можно писать: бинарник на месте и корень —
 * рабочее дерево. Без этого студия продолжает сохранять файлы, но история
 * версий и коммиты выключаются, о чём интерфейс говорит баннером.
 */
export async function gitStatus(): Promise<GitStatus> {
  try {
    await run('git', ['rev-parse', '--is-inside-work-tree'], { cwd: REPO_ROOT, timeout: 5000 })
    return { available: true }
  } catch (error) {
    const err = (error ?? {}) as ExecError
    if (err.code === 'ENOENT') return { available: false, reason: 'git не установлен' }
    if (err.killed) return { available: false, reason: 'git не ответил вовремя' }
    return { available: false, reason: `${REPO_ROOT} не git-репозиторий: выполните git init` }
  }
}

const LOG_FORMAT = '%H%x1f%h%x1f%aI%x1f%an%x1f%s%x1e'

function parseLog(stdout: string): Commit[] {
  return stdout
    .split('\x1e')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [sha, shortSha, date, author, subject] = entry.split('\x1f')
      return { sha, shortSha, date, author, subject }
    })
}

/** История одного файла. `--follow` переживает переименования. */
export async function fileHistory(relPath: string, limit = 40): Promise<Commit[]> {
  try {
    const stdout = await git([
      'log',
      `--max-count=${limit}`,
      `--format=${LOG_FORMAT}`,
      '--follow',
      '--',
      relPath,
    ])
    return parseLog(stdout)
  } catch {
    // Файл ещё не в индексе — истории просто нет, это не ошибка.
    return []
  }
}

/** Содержимое файла на конкретном коммите. */
export async function fileAtRev(relPath: string, sha: string): Promise<string | null> {
  if (!/^[0-9a-f]{7,40}$/i.test(sha)) throw new Error(`Недопустимый sha: ${sha}`)
  try {
    return await git(['show', `${sha}:${relPath}`])
  } catch {
    return null
  }
}

/** Есть ли у файла несохранённые в git изменения. */
export async function isDirty(relPath: string): Promise<boolean> {
  try {
    const stdout = await git(['status', '--porcelain', '--', relPath])
    return stdout.trim().length > 0
  } catch {
    return false
  }
}

export interface CommitResult {
  committed: boolean
  sha?: string
  reason?: string
}

/**
 * Коммитит переданные пути. Возвращает `committed: false`, если коммитить нечего
 * (сохранили тот же текст) или git отказал (нет репозитория, не настроен автор,
 * занят индекс) — файл к этому моменту уже на диске, и терять его из-за git
 * нельзя. Причина возвращается словами, а не кодом.
 *
 * Бросает только на пути вне белого списка: это ошибка программы, а не среды.
 */
export async function commitPaths(message: string, relPaths: string[]): Promise<CommitResult> {
  const paths = [...new Set(relPaths)].filter(Boolean)
  if (paths.length === 0) return { committed: false, reason: 'нет путей' }

  for (const relPath of paths) {
    if (!isCommittable(relPath)) {
      throw new Error(
        `Студия не коммитит этот путь: ${relPath}. Разрешено только ${committablePrefixes().join(', ')}`,
      )
    }
  }

  try {
    await git(['add', '--', ...paths])

    const staged = await git(['diff', '--cached', '--name-only', '--', ...paths])
    if (!staged.trim()) return { committed: false, reason: 'изменений нет' }

    // `--only` гарантирует, что в коммит попадут именно эти пути, даже если
    // в индексе застряло что-то ещё от параллельной сессии.
    await git(['commit', '--only', '--message', message, '--', ...paths])
    const sha = (await git(['rev-parse', 'HEAD'])).trim()
    return { committed: true, sha }
  } catch (error) {
    return { committed: false, reason: explainGitError(error) }
  }
}

/** Diff одного файла между двумя ревизиями, в unified-формате. */
export async function fileDiff(relPath: string, fromSha: string, toSha: string): Promise<string> {
  for (const sha of [fromSha, toSha]) {
    if (!/^[0-9a-f]{7,40}$/i.test(sha)) throw new Error(`Недопустимый sha: ${sha}`)
  }
  try {
    return await git(['diff', fromSha, toSha, '--', relPath])
  } catch {
    return ''
  }
}
