// Извлекатель постов Threads из DOM. Выполняется через `browser eval`.
//
// Опора на aria-label кнопок, а не на классы: классы у Threads обфусцированы и
// меняются при каждом деплое, подписи кнопок живут годами.
//
// Порядок кнопок в панели действий фиксирован: лайк, ответ, репост, цитата.
// Считаем именно по кнопкам, а не по числам в тексте карточки: у поста с нулём
// ответов число не отрисовывается, и разбор "последних четырёх чисел" молча
// сползает на соседнюю метрику.
(() => {
  const LABELS = ['Поставить', 'Ответ', 'Сделать репост', 'Поделиться'];

  const svgsIn = (el) => [...el.querySelectorAll('svg[aria-label]')];
  const labelOf = (svg) => svg.getAttribute('aria-label') || '';
  const findSvg = (el, prefix) => svgsIn(el).find((s) => labelOf(s).startsWith(prefix));
  const hasAllActions = (el) => LABELS.every((l) => findSvg(el, l));

  // Число под кнопкой: поднимаемся от иконки, пока не найдём узел, чей текст
  // целиком является числом. Пусто значит ноль.
  const countFor = (card, prefix) => {
    const svg = findSvg(card, prefix);
    if (!svg) return null;
    let node = svg.parentElement;
    for (let i = 0; i < 6 && node && node !== card; i++) {
      const t = (node.innerText || '').trim();
      if (t === '') return 0;
      const m = t.match(/^([\d  ., ]+)([KMКМтыс.]*)$/i);
      if (m) return parseCount(t);
      node = node.parentElement;
    }
    return 0;
  };

  // "1 234" -> 1234, "12,3K" -> 12300. Threads сокращает крупные числа.
  const parseCount = (raw) => {
    const s = raw.replace(/[  \s]/g, '').trim();
    const m = s.match(/^([\d.,]+)\s*([KMКМ])?/i);
    if (!m) return null;
    const num = parseFloat(m[1].replace(',', '.'));
    if (Number.isNaN(num)) return null;
    const suffix = (m[2] || '').toUpperCase();
    if (suffix === 'K' || suffix === 'К') return Math.round(num * 1000);
    if (suffix === 'M' || suffix === 'М') return Math.round(num * 1000000);
    return Math.round(num);
  };

  const out = [];
  const seen = new Set();
  // Карточки, которые уже отдали пост. Если пост цитирует другой пост, внутри
  // одной карточки лежат две ссылки на посты, но панель действий и её числа
  // общие. Без этой проверки цитируемый пост попадал в базу отдельной записью
  // с метриками родителя.
  const claimed = new Set();

  document.querySelectorAll('a[href*="/post/"]').forEach((a) => {
    const m = (a.getAttribute('href') || '').match(/^\/@([\w.\-]+)\/post\/([\w-]+)/);
    if (!m) return;
    const [, author, id] = m;
    if (seen.has(id)) return;

    // Поднимаемся от ссылки до карточки: это ближайший предок, в котором есть
    // все четыре кнопки действий.
    let card = a;
    for (let i = 0; i < 15 && card.parentElement; i++) {
      card = card.parentElement;
      if (hasAllActions(card)) break;
    }
    if (!hasAllActions(card)) return;
    if (claimed.has(card)) return;
    claimed.add(card);
    seen.add(id);

    const timeEl = card.querySelector('time[datetime]');
    const text = (card.innerText || '')
      .split('\n')
      .slice(1) // первая строка — ник автора
      .join('\n')
      .trim();

    out.push({
      id,
      author,
      url: 'https://www.threads.com/@' + author + '/post/' + id,
      datetime: timeEl ? timeEl.getAttribute('datetime') : null,
      date_text: timeEl ? (timeEl.innerText || '').trim() : null,
      text,
      likes: countFor(card, 'Поставить'),
      replies: countFor(card, 'Ответ'),
      reposts: countFor(card, 'Сделать репост'),
      quotes: countFor(card, 'Поделиться'),
      has_video: !!card.querySelector('video'),
      img_count: card.querySelectorAll('img[src*="cdninstagram"], img[src*="fbcdn"]').length,
      is_carousel: /\n\d+\n\/\n\d+\n/.test(card.innerText || ''),
    });
  });

  return JSON.stringify(out);
})()
