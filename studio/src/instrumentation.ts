/**
 * Точка входа Next при старте сервера. Сама проверка живёт в lib/startup.ts:
 * этот файл собирается и для edge, где `node:fs` недоступен, поэтому модуль
 * с ним подключается только внутри ветки node-рантайма — так, как советует
 * документация Next, иначе бандлер тянет его в оба бандла и предупреждает.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { logStartup } = await import('./lib/startup')
    await logStartup()
  }
}
