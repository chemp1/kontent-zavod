import fs from 'node:fs'
import matter from 'gray-matter'

/**
 * Общие мелочи разбора markdown с фронтматтером. Вынесены из `telegram.ts`,
 * когда за сводками появился второй читатель — контент-план.
 */

/**
 * Разбор с запасным вариантом: незакавыченное двоеточие в заголовке — обычная
 * опечатка, и она роняет YAML целиком. Материал с битым фронтматтером должен
 * открыться текстом, а не утащить за собой весь раздел.
 */
export function parseFile(abs: string): { data: Record<string, unknown>; content: string } {
  const raw = fs.readFileSync(abs, 'utf8')
  try {
    const parsed = matter(raw)
    return { data: parsed.data as Record<string, unknown>, content: parsed.content }
  } catch {
    const body = raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '')
    return { data: {}, content: body }
  }
}

export function str(data: Record<string, unknown>, key: string, fallback = ''): string {
  const value = data[key]
  if (typeof value === 'string') return value
  // Дата без кавычек приходит из YAML объектом Date, а не строкой.
  if (value instanceof Date) return value.toISOString().slice(0, 10)
  return typeof value === 'number' ? String(value) : fallback
}

export function num(data: Record<string, unknown>, key: string): number {
  const value = data[key]
  if (typeof value === 'number') return value
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value)
  }
  return 0
}
