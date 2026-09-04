'use client'

import { useState } from 'react'

/**
 * Копирует пост для вставки в Telegram. В буфер кладутся сразу два формата:
 * text/html (жирный заголовок, живые ссылки — десктопный клиент вставит их
 * как форматирование) и text/plain на случай клиентов без rich-вставки.
 */

function escapeHtml(text: string): string {
  return text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}

function toTelegramHtml(markdown: string): string {
  const lines = escapeHtml(markdown.trim())
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .split('\n')
  const firstIndex = lines.findIndex((line) => line.trim() !== '')
  if (firstIndex >= 0 && !lines[firstIndex].startsWith('<b>')) {
    lines[firstIndex] = `<b>${lines[firstIndex]}</b>`
  }
  return lines.join('<br>')
}

function toPlainText(markdown: string): string {
  return markdown
    .trim()
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text: string, url: string) =>
      text === url ? url : `${text} - ${url}`,
    )
    .replace(/\*\*([^*]+)\*\*/g, '$1')
}

export function CopyPostButton({ markdown }: { markdown: string }) {
  const [state, setState] = useState<'idle' | 'done' | 'error'>('idle')

  async function copy() {
    const plain = toPlainText(markdown)
    try {
      if (typeof ClipboardItem !== 'undefined') {
        await navigator.clipboard.write([
          new ClipboardItem({
            'text/plain': new Blob([plain], { type: 'text/plain' }),
            'text/html': new Blob([toTelegramHtml(markdown)], { type: 'text/html' }),
          }),
        ])
      } else {
        await navigator.clipboard.writeText(plain)
      }
      setState('done')
    } catch {
      setState('error')
    }
    setTimeout(() => setState('idle'), 2500)
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="rounded-md border border-border px-3 py-1 text-sm text-text hover:border-accent hover:text-accent"
    >
      {state === 'idle' && 'Скопировать для телеги'}
      {state === 'done' && 'Скопировано - вставляйте'}
      {state === 'error' && 'Не удалось скопировать'}
    </button>
  )
}
