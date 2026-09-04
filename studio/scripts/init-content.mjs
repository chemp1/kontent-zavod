#!/usr/bin/env node
/**
 * Раскладывает стартовую `content/` из `templates/content/` в корень:
 * `$STUDIO_ROOT/content` или, без переменной, `../content` относительно studio/.
 *
 * Существующие файлы не трогает — скрипт можно запускать повторно, когда в
 * шаблоне появится новая папка, и он доложит только то, что создал.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = process.env.STUDIO_ROOT
  ? path.resolve(process.env.STUDIO_ROOT)
  : path.resolve(here, '..', '..')
const templates = path.join(here, '..', 'templates', 'content')
const target = path.join(root, 'content')

function walk(dir) {
  const out = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walk(abs))
    else if (entry.isFile()) out.push(abs)
  }
  return out
}

const created = []
const kept = []

for (const source of walk(templates)) {
  const rel = path.relative(templates, source)
  const dest = path.join(target, rel)
  if (fs.existsSync(dest)) {
    kept.push(rel)
    continue
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  fs.copyFileSync(source, dest)
  created.push(rel)
}

console.log(`Корень: ${root}`)
if (created.length === 0) {
  console.log(`content/ уже на месте, новых файлов нет (${kept.length} оставлено как есть)`)
} else {
  console.log(`Создано в content/ (${created.length}):`)
  for (const rel of created) console.log(`  + ${rel}`)
  if (kept.length > 0) console.log(`Оставлено как есть: ${kept.length}`)
}
