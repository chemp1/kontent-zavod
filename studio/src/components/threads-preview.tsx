'use client'

import { useState } from 'react'

/**
 * Тестовое отображение ветки Threads: посты показываются так, как будут
 * выглядеть в приложении, — тёмная лента, аватар, коннектор между постами.
 *
 * Материал площадки `threads` разбивается на посты по строке `---` — так же
 * серии оформляются в черновиках. Под каждым постом — две проверки из замера
 * ленты 19.08: лимит площадки 500 знаков и крючок первой строки 70–90 знаков,
 * который должен целиком попасть в превью ленты.
 */

const POST_LIMIT = 500
const HOOK_MIN = 70
const HOOK_MAX = 90

/** Ник и буква на аватаре — из `content/studio.json`, страница передаёт их сюда. */
export interface PreviewAuthor {
  handle: string
  initial: string
}

interface ThreadImage {
  alt: string
  src: string
}

interface ThreadPost {
  text: string
  firstLine: string
  images: ThreadImage[]
}

/** Markdown-картинка на отдельной строке: медиа поста, а не часть текста. */
const IMAGE_LINE = /^!\[([^\]]*)\]\(([^)\s]+)\)$/

function splitPosts(body: string): ThreadPost[] {
  return body
    .split(/\n\s*---\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((raw) => {
      const images: ThreadImage[] = []
      const lines = raw.split('\n').filter((line) => {
        const m = line.trim().match(IMAGE_LINE)
        if (m) {
          images.push({ alt: m[1], src: m[2] })
          return false
        }
        return true
      })
      // Медиа не входит ни в текст для копирования, ни в счётчик знаков.
      const text = lines.join('\n').replace(/\n{3,}/g, '\n\n').trim()
      return { text, firstLine: text.split('\n')[0] ?? '', images }
    })
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      setTimeout(() => setDone(false), 2000)
    } catch {
      // В браузере без clipboard API кнопка просто не срабатывает.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="rounded-md border border-[#333] px-2 py-0.5 text-xs text-[#999] transition-colors hover:border-[#666] hover:text-white"
    >
      {done ? 'Скопировано' : 'Скопировать'}
    </button>
  )
}

export function ThreadsPreview({ body, author }: { body: string; author: PreviewAuthor }) {
  const posts = splitPosts(body)
  if (posts.length === 0) return null

  return (
    <div className="mt-4 rounded-xl bg-[#0a0a0a] p-4 font-[system-ui,sans-serif] sm:p-6">
      {posts.map((post, index) => {
        const chars = post.text.length
        const hook = post.firstLine.length
        const overLimit = chars > POST_LIMIT
        const hookOk = hook >= HOOK_MIN && hook <= HOOK_MAX
        const last = index === posts.length - 1

        return (
          <div key={index} className="flex gap-3">
            {/* Аватар и коннектор ветки, как в самом Threads. */}
            <div className="flex flex-col items-center">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#4f5bd5] to-[#962fbf] text-sm font-semibold text-white">
                {author.initial}
              </div>
              {!last ? <div className="my-1 w-0.5 grow rounded bg-[#2e2e2e]" /> : null}
            </div>

            <div className={`min-w-0 flex-1 ${last ? '' : 'pb-5'}`}>
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-semibold text-white">{author.handle}</span>
                <span className="text-xs text-[#777]">
                  {index + 1}/{posts.length}
                </span>
                <span className="ml-auto">
                  <CopyButton text={post.text} />
                </span>
              </div>

              <div className="mt-1 text-[15px] leading-snug whitespace-pre-wrap text-[#f3f5f7]">
                {post.text}
              </div>

              {post.images.length > 0 ? (
                <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
                  {post.images.map((img) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      key={img.src}
                      src={img.src}
                      alt={img.alt}
                      title={img.alt}
                      className="h-56 w-auto max-w-[85%] shrink-0 rounded-lg border border-[#2e2e2e] object-cover"
                    />
                  ))}
                </div>
              ) : null}

              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <span className={overLimit ? 'font-medium text-[#ff6b5e]' : 'text-[#777]'}>
                  {chars} / {POST_LIMIT} знаков
                </span>
                <span className={hookOk ? 'text-[#777]' : 'text-[#e0b64a]'}>
                  крючок {hook} зн{hookOk ? '' : ` (цель ${HOOK_MIN}–${HOOK_MAX})`}
                </span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
