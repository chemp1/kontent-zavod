#!/usr/bin/env python3
"""Тесты линтера и калибратора. Только stdlib: `python3 test_lint.py`.

Три группы:
  1. Линтер с встроенными порогами ловит типовой машинный текст и пропускает живой.
  2. Калибратор выводит пороги по правилам класса на синтетическом корпусе.
  3. Если рядом лежит корпус автора и thresholds.json - файл совпадает с пересчётом
     (то есть его не правили руками) и линтер даёт на корпусе разумный балл.
"""

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calibrate  # noqa: E402
import lint  # noqa: E402

SLOP = """# Почему ИИ-агенты меняют правила игры в контенте

Важно понимать: мы живем в эпоху, когда создание контента перестало быть узким местом. Это не просто инструмент. Это новая парадигма работы с текстом.

Ключевой вывод — автоматизация действительно способна обеспечить кратный рост производительности:

— скорость создания материалов увеличивается в разы
— качество остается на стабильно высоком уровне
— масштабирование не требует расширения команды

Более того, данный подход позволяет выстроить системный процесс. И это нормально, что переход занимает время. Таким образом, каждый может найти свой путь к эффективности.
"""

LIVE = """Про линтер

Написал себе линтер для постов. Не потому что хотел, а потому что три вечера подряд ловил у модели одно и то же: длинные тире, канцелярские связки и списки через тире. Надоело)

Идея простая. Берём корпус своих постов, считаем, как часто в них что встречается, и сравниваем черновик с этой нормой. Не с «хорошим текстом вообще», а со своим.

Что вышло. Скрипт на триста строк, без зависимостей. Прогоняю черновик, он говорит: тут четыре тире (у тебя норма одно), тут нет ни одной скобки (у тебя они в девяти постах из десяти), тут ритм ровный, как у робота.

Самое смешное случилось на второй день. Линтер забраковал мой собственный пост. Короткий, на девятьсот знаков, без единого «кажется». Оказалось, я так и пишу короткие посты, а порог был снят с длинных. Пришлось разводить по длине.

В общем, инструмент калибруется по автору, а не по идеалу. Кажется, это главное, что я из этой истории вынес.

Мне интересно, есть ли у вас такие же приметы, по которым вы узнаёте нейросетевую редактуру в своих текстах?
"""


def make_post(rng, chars, dashes=0, hedge=True, smiley=True, first_person=True):
    """Синтетический пост с заданными свойствами."""
    words = ["станок", "заказ", "клиент", "смета", "доска", "фрезер", "цех", "неделя",
             "утро", "таблица", "скрипт", "письмо", "склад", "лак", "сборка", "поставка"]
    body = []
    while sum(len(x) for x in body) < chars:
        n = rng.randint(4, 14)
        body.append(" ".join(rng.choice(words) for _ in range(n)).capitalize() + ".")
        if rng.random() < 0.3:
            body.append("\n")
    text = "Заголовок поста\n\n" + " ".join(body)
    if first_person:
        text += "\nЯ так и делаю."
    if hedge:
        text += " Кажется, работает."
    if smiley:
        text += " Посмотрим)"
    if dashes:
        text += "\n" + " — ".join(["x"] * (dashes + 1))
    return text


class LinterTests(unittest.TestCase):
    def setUp(self):
        self.T = json.loads(json.dumps(lint.DEFAULTS))

    def test_slop_is_caught(self):
        checks = lint.analyze(SLOP, self.T)
        stops = {c.label for c in checks if c.level == "stop"}
        for label in ("Длинное тире", "Буллеты через тире", "Служебные обороты",
                      "Псевдотерапевтический регистр", "«Это не X. Это Y»"):
            self.assertIn(label, stops)
        _, _, score = lint.score_of(checks, self.T)
        self.assertLess(score, 30)

    def test_live_text_passes(self):
        checks = lint.analyze(LIVE, self.T)
        stops = [c.label for c in checks if c.level == "stop"]
        self.assertEqual(stops, [])
        _, _, score = lint.score_of(checks, self.T)
        self.assertGreaterEqual(score, 88)

    def test_measure_counts(self):
        m = lint.measure(SLOP, self.T, lint.compile_patterns(self.T))
        self.assertEqual(m["dash"], 4)
        self.assertEqual(m["dash_bullets"], 3)
        self.assertIn("важно понимать", m["banned"])
        self.assertFalse(m["first_person"])
        self.assertEqual(m["smileys"], 0)

    def test_off_level_disables_check(self):
        self.T["dash"]["level"] = "off"
        checks = lint.analyze(SLOP, self.T)
        self.assertNotIn("Длинное тире", {c.label for c in checks})

    def test_deep_merge_partial_file(self):
        T = lint.deep_merge(lint.DEFAULTS, {"length": {"ok_min": 100}, "meta": {"corpus_label": "x"}})
        self.assertEqual(T["length"]["ok_min"], 100)
        self.assertEqual(T["length"]["ok_max"], lint.DEFAULTS["length"]["ok_max"])
        self.assertEqual(T["meta"]["corpus_label"], "x")

    def test_pick_bucket(self):
        b = [{"below": 1000, "id": 0}, {"below": 1500, "id": 1}, {"below": None, "id": 2}]
        self.assertEqual(lint.pick_bucket(b, 500)["id"], 0)
        self.assertEqual(lint.pick_bucket(b, 1000)["id"], 1)
        self.assertEqual(lint.pick_bucket(b, 9000)["id"], 2)

    def test_frontmatter_stripped(self):
        self.assertEqual(lint.strip_frontmatter("---\na: 1\n---\nтекст"), "текст")


class CalibrateTests(unittest.TestCase):
    def synthetic(self, **kw):
        rng = random.Random(7)
        posts = []
        for i in range(60):
            chars = rng.choice([600, 800, 1200, 1400, 1800, 2100])
            posts.append((f"2026-01-{i % 28 + 1:02d}", make_post(rng, chars, **kw)))
        return posts

    def test_dash_free_author_gets_stop(self):
        T, _ = calibrate.calibrate(self.synthetic(dashes=0), lint.DEFAULTS, [1000, 1500], 10, "t")
        self.assertEqual(T["dash"]["level"], "stop")
        self.assertLessEqual(T["dash"]["max_per_post"], 1)

    def test_dash_heavy_author_gets_off(self):
        T, _ = calibrate.calibrate(self.synthetic(dashes=5), lint.DEFAULTS, [1000, 1500], 10, "t")
        self.assertEqual(T["dash"]["level"], "off")

    def test_presence_markers_follow_corpus(self):
        T, _ = calibrate.calibrate(self.synthetic(smiley=True, hedge=True), lint.DEFAULTS, [1000, 1500], 10, "t")
        self.assertEqual(T["smileys"]["buckets"][1]["missing"], "stop")
        self.assertEqual(T["hedges"]["buckets"][2]["missing"], "stop")
        T2, _ = calibrate.calibrate(self.synthetic(smiley=False, hedge=False), lint.DEFAULTS, [1000, 1500], 10, "t")
        self.assertEqual(T2["smileys"]["buckets"][1]["missing"], "ok")
        self.assertEqual(T2["hedges"]["buckets"][2]["missing"], "ok")

    def test_small_bucket_lowers_level(self):
        posts = self.synthetic()[:12]  # мало постов - stop не выдаём
        T, _ = calibrate.calibrate(posts, lint.DEFAULTS, [1000, 1500], 30, "t")
        for b in T["smileys"]["buckets"]:
            self.assertNotEqual(b["missing"], "stop")
        self.assertTrue(any("понижен" in w for w in T["meta"]["warnings"]))

    def test_pin_keeps_seed_level(self):
        seed = json.loads(json.dumps(lint.DEFAULTS))
        seed["dash"] = {"max_per_post": 1, "level": "stop", "pin": True}
        T, _ = calibrate.calibrate(self.synthetic(dashes=5), seed, [1000, 1500], 10, "t")
        self.assertEqual(T["dash"]["level"], "stop")

    def test_never_phrase_absent_is_stop(self):
        T, _ = calibrate.calibrate(self.synthetic(), lint.DEFAULTS, [1000, 1500], 10, "t")
        self.assertEqual(T["never"]["Псевдотерапевтический регистр"]["level"], "stop")
        self.assertEqual(T["banned_phrases"]["level"], "stop")

    def test_read_corpus_formats(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "c.json").write_text(json.dumps([{"date": "2026-01-01T10:00:00+00:00", "text": "a b c"}]), encoding="utf-8")
            (d / "posts").mkdir()
            (d / "posts" / "2026-02-02-x.md").write_text("---\nid: 1\n---\nпост", encoding="utf-8")
            (d / "c.md").write_text("# К\n\n## 2026-03-03 (1K views)\n\nтекст один\n\n---\n\n## 2026-03-04 (2K views)\n\nтекст два\n\n---\n", encoding="utf-8")
            self.assertEqual(calibrate.read_corpus(d / "c.json"), [("2026-01-01", "a b c")])
            self.assertEqual(calibrate.read_corpus(d / "posts"), [("2026-02-02", "пост")])
            self.assertEqual(calibrate.read_corpus(d / "c.md"), [("2026-03-03", "текст один"), ("2026-03-04", "текст два")])


class AuthorCorpusTests(unittest.TestCase):
    """Запускаются, только если рядом есть корпус автора."""

    @classmethod
    def setUpClass(cls):
        root = HERE.parents[3] if len(HERE.parents) > 3 else HERE
        cls.corpus = next((p for p in (root / "posts" / "voice" / "corpus" / "channel.json",
                                       root / "voice" / "corpus" / "channel.json") if p.is_file()), None)
        cls.thresholds = next((p for p in (root / "posts" / "voice" / "thresholds.json",
                                           root / "voice" / "thresholds.json") if p.is_file()), None)

    def test_thresholds_match_recalculation(self):
        if not (self.corpus and self.thresholds):
            self.skipTest("нет корпуса или thresholds.json")
        saved = json.loads(self.thresholds.read_text(encoding="utf-8"))
        posts = calibrate.read_corpus(self.corpus)
        edges = [saved["buckets"]["short_below"], saved["buckets"]["medium_below"]]
        seed = json.loads(json.dumps(lint.DEFAULTS))
        seed_file = self.thresholds.with_name("seed.json")  # словари автора, если есть
        if seed_file.is_file():
            seed = lint.deep_merge(seed, json.loads(seed_file.read_text(encoding="utf-8")))
        T, _ = calibrate.calibrate(posts, seed, edges, 30, saved["meta"]["corpus_label"])
        for d in (saved, T):
            d["meta"].pop("generated", None)
        self.assertEqual(saved, T, "thresholds.json разошёлся с пересчётом - его правили руками?")

    def test_corpus_scores_well_under_own_thresholds(self):
        if not (self.corpus and self.thresholds):
            self.skipTest("нет корпуса или thresholds.json")
        T = lint.deep_merge(lint.DEFAULTS, json.loads(self.thresholds.read_text(encoding="utf-8")))
        posts = calibrate.read_corpus(self.corpus)
        scores = [lint.score_of(lint.analyze(t, T), T)[2] for _, t in posts]
        median = sorted(scores)[len(scores) // 2]
        self.assertGreaterEqual(median, 80, f"медиана балла по своему корпусу {median}")


if __name__ == "__main__":
    unittest.main(verbosity=1)