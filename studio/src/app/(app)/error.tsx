'use client'

import Link from 'next/link'

/**
 * Граница ошибок для разделов: битый frontmatter или отсутствующий файл не
 * должны ронять всё приложение. Шапка с навигацией остаётся — она в layout,
 * который эта граница не оборачивает.
 */
export default function AppError({
  error,
  retry,
}: {
  error: Error & { digest?: string }
  retry: () => void
}) {
  return (
    <div className="mx-auto max-w-xl rounded-lg border border-border bg-surface p-6">
      <h1 className="font-serif text-xl font-semibold">Страница не открылась</h1>
      <p className="mt-2 text-sm break-words text-muted">{error.message}</p>
      {error.digest ? (
        <p className="mt-1 font-mono text-xs text-muted">digest: {error.digest}</p>
      ) : null}
      <div className="mt-5 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={() => retry()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white"
        >
          Попробовать снова
        </button>
        <Link href="/library" className="text-sm text-accent underline">
          В библиотеку
        </Link>
      </div>
    </div>
  )
}
