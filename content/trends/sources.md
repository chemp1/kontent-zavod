---
feeds:
  - id: yc
    title: "Y Combinator"
    kind: video
    filter: none
    url: "https://www.youtube.com/feeds/videos.xml?channel_id=UCcefcZRL2oaA_uBNeo5UOWg"
  - id: sequoia
    title: "Sequoia Capital"
    kind: video
    filter: none
    url: "https://www.youtube.com/feeds/videos.xml?channel_id=UCWrF0oN6unbXrWsTN7RctTw"
  - id: a16z
    title: "a16z"
    kind: video
    filter: none
    url: "https://www.youtube.com/feeds/videos.xml?channel_id=UC9cn0TuPq4dnbTY-CBsm8XA"
  - id: techcrunch
    title: "TechCrunch"
    kind: article
    filter: keywords
    url: "https://techcrunch.com/feed/"
  - id: theverge
    title: "The Verge"
    kind: article
    filter: keywords
    url: "https://www.theverge.com/rss/index.xml"
  - id: hn
    title: "Hacker News"
    kind: discussion
    filter: keywords
    url: "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=50"
keywords:
  - ai
  - agent
  - agents
  - llm
  - gpt
  - claude
  - anthropic
  - openai
  - gemini
  - copilot
  - vibe coding
  - developer tools
  - devtools
  - founder
  - founders
  - startup
  - startups
  - saas
  - product
  - community
  - no-code
  - automation
limit_per_run: 6
---

Что мониторит `tools/trend-watch/`. Правится этот файл — меняется лента: сборщик читает
его на каждом прогоне, пересобирать ничего не нужно.

**Каналы фондов идут без фильтра** (`filter: none`): там уже человек отобрал, о чём
говорить, и терять выпуск из-за отсутствия слова «ai» в заголовке глупо. У новостных
лент фильтр по ключевым словам обязателен: TechCrunch за сутки выдаёт полсотни
заметок, из которых автору интересны единицы.

`limit_per_run` — потолок карточек за прогон. Он тут не ради экономии токенов,
а против ленты, в которую перестаёшь заглядывать: шесть карточек в день читаются,
тридцать — нет.

**Id канала YouTube, а не @handle.** RSS понимает только `channel_id=UC…`; хендл
резолвится один раз руками:

```bash
curl -s -A "Mozilla/5.0" -L https://www.youtube.com/@<handle> | grep -o '"externalId":"UC[A-Za-z0-9_-]*"' | head -1
```
