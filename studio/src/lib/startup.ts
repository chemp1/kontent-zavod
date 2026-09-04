import fs from 'node:fs'

import { gitStatus } from './git'
import { REPO_ROOT, STUDIO_CONFIG_FILE } from './paths'

/**
 * Одна строка в лог при старте сервера: где корень, нашёлся ли `studio.json`,
 * доступен ли git. Когда студия поднята не над той папкой, это видно сразу,
 * а не по пустой библиотеке. Никогда не бросает — старт важнее диагностики.
 *
 * Модуль только для node-рантайма: его подключает `instrumentation.ts`
 * динамическим импортом под проверкой `NEXT_RUNTIME`.
 */
export async function logStartup(): Promise<void> {
  try {
    const config = fs.existsSync(STUDIO_CONFIG_FILE) ? 'найден' : 'не найден, работаю с дефолтами'
    const git = await gitStatus()
    console.log(
      `[studio] корень ${REPO_ROOT}; studio.json ${config}; git ${
        git.available ? 'доступен' : `недоступен (${git.reason})`
      }`,
    )
  } catch (error) {
    console.warn(
      `[studio] проверка окружения при старте не удалась: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
}
