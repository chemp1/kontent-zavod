import Link from 'next/link'

import { Badge, EmptyState, PageHeader, formatDate } from '@/components/ui'
import { listReports } from '@/lib/reports'

export const dynamic = 'force-dynamic'

export default function ReportsPage() {
  const reports = listReports()

  return (
    <>
      <PageHeader
        title="Отчёты"
        description="Разборы с цифрами: что заходит на площадках, как ведут себя посты, чему учит чужой опыт. Каждый отчёт — снимок на дату, а не вечная истина."
      />

      {reports.length === 0 ? (
        <EmptyState
          title="Пока ни одного отчёта"
          hint="Отчёт появляется здесь сам, как только в content/reports/ ложится markdown-файл. Пересборка не нужна."
        />
      ) : (
        <ul className="space-y-3">
          {reports.map((report) => (
            <li key={report.slug}>
              <Link
                href={`/reports/${report.slug}`}
                className="block rounded-lg border border-border bg-surface p-4 transition-colors hover:border-accent"
              >
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="font-serif text-lg font-medium">{report.title}</span>
                  {report.date ? (
                    <span className="text-sm text-muted">{formatDate(report.date)}</span>
                  ) : null}
                </div>

                {report.summary ? (
                  <p className="mt-1.5 text-sm text-muted">{report.summary}</p>
                ) : null}

                {report.tags.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {report.tags.map((tag) => (
                      <Badge key={tag} tone="neutral">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
