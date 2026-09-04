import Link from 'next/link'

/** Адрес вне всех разделов. Рисуется в корневом layout, без шапки. */
export default function RootNotFound() {
  return (
    <div className="flex min-h-full flex-1 items-center justify-center px-5 py-16">
      <div className="max-w-md text-center">
        <h1 className="font-serif text-2xl font-semibold tracking-tight">Страница не найдена</h1>
        <p className="mt-2 text-sm text-muted">Такого адреса в студии нет.</p>
        <Link href="/library" className="mt-4 inline-block text-sm text-accent underline">
          В библиотеку
        </Link>
      </div>
    </div>
  )
}
