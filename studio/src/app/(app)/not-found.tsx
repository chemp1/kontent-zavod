import Link from 'next/link'

/** Сюда попадает `notFound()` из страниц разделов: нет идеи, слота, отчёта. */
export default function AppNotFound() {
  return (
    <div className="mx-auto max-w-xl rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <p className="font-medium">Такого здесь нет</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">
        Файла с таким адресом нет на диске — его могли переименовать или удалить.
      </p>
      <Link href="/library" className="mt-4 inline-block text-sm text-accent underline">
        В библиотеку
      </Link>
    </div>
  )
}
