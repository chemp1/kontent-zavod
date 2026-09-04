/**
 * Приложение может жить как в корне (`npm run dev` на 127.0.0.1:5180), так и на
 * подпути за чужим nginx (`https://example.com/studio`).
 *
 * Next сам подставляет basePath в `<Link>` и в навигацию роутера, но **не**
 * трогает строки, которые мы передаём в `fetch`. Поэтому все обращения к своим
 * API идут через `apiUrl()` — иначе на подпути они улетят в корень домена,
 * где живёт что-то чужое, и вернут его 404 вместо нашего ответа.
 */
export const BASE_PATH = process.env.NEXT_PUBLIC_STUDIO_BASE_PATH ?? ''

export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${BASE_PATH}${normalized}`
}
