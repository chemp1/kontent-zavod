import type { NextConfig } from 'next'

/**
 * `STUDIO_BASE_PATH` задаётся, когда приложение стоит за nginx на подпути
 * (`https://example.com/studio`). Локально переменной нет, и приложение
 * живёт в корне — поэтому `npm run dev` работает без настройки.
 * Значение вшивается в сборку, поэтому задаётся и при `next build`,
 * и при `next start` — удобнее всего через `.env.production`.
 *
 * Значение дублируется в `NEXT_PUBLIC_*`, чтобы клиентские компоненты могли
 * собирать им адреса своих API (см. lib/base-path.ts).
 */
const basePath = process.env.STUDIO_BASE_PATH?.replace(/\/$/, '') || ''

const nextConfig: NextConfig = {
  ...(basePath ? { basePath } : {}),
  env: {
    NEXT_PUBLIC_STUDIO_BASE_PATH: basePath,
  },
}

export default nextConfig
