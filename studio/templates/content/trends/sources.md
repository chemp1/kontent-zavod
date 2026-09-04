---
feeds:
  - id: hn
    title: "Hacker News"
    kind: discussion
    filter: keywords
    url: "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=50"
  - id: techcrunch
    title: "TechCrunch"
    kind: article
    filter: keywords
    url: "https://techcrunch.com/feed/"
keywords:
  - ai
  - agents
  - llm
  - startup
  - product
limit_per_run: 6
---

Какие фиды обходит внешний сборщик трендов. Студия этот файл только читает:
по нему подписи источников в ленте совпадают с тем, что реально опрашивается.

`kind` — `video`, `article` или `discussion`; `filter: keywords` оставляет из
ленты только записи с одним из `keywords` в заголовке, `filter: none` берёт всё
подряд (годится для каналов, где отбор уже сделал человек).

`limit_per_run` — потолок карточек за прогон. Он тут не ради экономии, а против
ленты, в которую перестаёшь заглядывать: шесть карточек в день читаются,
тридцать — нет.
