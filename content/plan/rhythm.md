---
rubrics:
  - key: case
    label: "Сделал руками"
    hint: "Вайб-кодинг кейс: что построил, сколько занял, что сломалось, скрин"
  - key: teza
    label: "Заострённый тезис"
    hint: "Одна мысль про AI, с которой можно спорить. Концовка — вопрос или открытый край"
  - key: skill
    label: "Скилл-пост"
    hint: "Конкретный приём, промпт, инструкция — применимо за вечер"
  - key: people
    label: "Комьюнити и люди"
    hint: "Наблюдения из десяти лет нетворкинга — фактура, которой нет у AI-авторов"
  - key: personal
    label: "Личное"
    hint: "Честная история с выводом, в том числе фейл"
  - key: series
    label: "Серия"
    hint: "Одна тема цепочкой из 3–5 самостоятельных постов"
  - key: longread
    label: "Лонгрид"
    hint: "Разбор, который не влезает в пост"
grid:
  - platform: threads
    time: "09:00"
    rubric: teza
    days: [mon, tue, wed, thu, fri, sat, sun]
  - platform: threads
    time: "14:00"
    rubric: case
    days: [mon, tue, wed, thu, fri, sat, sun]
  - platform: threads
    time: "20:00"
    rubric: personal
    days: [mon, tue, wed, thu, fri, sat, sun]
  - platform: telegram
    time: "12:00"
    rubric: case
    days: [tue, fri]
  - platform: x
    time: "10:00"
    rubric: teza
    days: [mon, wed, fri]
  - platform: linkedin
    time: "10:00"
    rubric: case
    days: [wed]
  - platform: facebook
    time: "12:00"
    rubric: people
    days: [sat]
  - platform: instagram
    time: "19:00"
    rubric: personal
    days: [thu]
  - platform: youtube
    time: "18:00"
    rubric: skill
    days: [mon]
---

Ритм — это привычка, а не обязательство. Календарь рисует по этой сетке бледные
слоты там, где день ещё пустой, и считает наверху «сколько из скольких».

**Threads — единственная строка, снятая с реальности**: три поста в день и деление
на утро/день/вечер взяты из замера по 409 постам ([отчёт](../reports/2026-08-19-threads-chto-zahodit.md)),
где ритм уже обоснован замером по 409 чужим постам. Время — гипотеза, калибруется
по первому месяцу.

**Остальные строки — заготовка.** Числа поставлены по здравому смыслу, а не по
замеру: телега два раза в неделю, LinkedIn и Facebook по разу, Instagram раз,
YouTube по понедельникам. Поправить нагрузку = поправить этот файл; слоты,
которые уже заведены, от этого не пострадают.

Рубрики — те же шесть столпов, что в контент-плане Threads, плюс лонгрид.
Пропорция на старте: кейсы и тезисы поровну впереди, скиллы и комьюнити следом.
