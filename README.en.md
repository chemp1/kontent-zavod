# kontent-zavod

**[Русский](README.md)**

A content factory around a single author: how to grow a pipeline of texts in one person's
voice out of a text file about that person, without turning it into a slop factory.

The author is not in this repo. `voice/` holds a fictional person with a corpus of posts
so that everything runs out of the box. Replace them with yourself.

Everything here is tuned for Russian-language text. The linter's dictionaries and the
platform registers are Russian; the method and the tooling are language-agnostic.

## What's inside

- **Voice linter.** `lint.py` compares a draft not with "good writing" but with how a
  specific author writes: dashes, smileys, hedges, first person, rhythm, length.
  Thresholds are not invented; `calibrate.py` derives them from the author's corpus.
- **Two skills for Claude Code.** The writer drafts and edits in the voice from `voice/`;
  the corrector proofreads and strips the AI-edited feel. Skills carry the method;
  everything about the author lives in data.
- **Studio.** A web UI over the text folder: ideas, content plan, trends, memory, reports,
  a map of the skill. Files are the source of truth, git is the history. It never publishes.
- **Input collectors.** Trends from feeds with angles per platform, ideas mined from
  your own calls, platform measurements.
- **Method and pitfalls.** `docs/` explains why, which boundaries hold, and what already
  went wrong.

## Quick start

```bash
git clone https://github.com/chemp1/kontent-zavod.git && cd kontent-zavod

# linter on two drafts by the fictional author: a live one and a "written by an AI in general" one
python3 .claude/skills/corrector/scripts/lint.py voice/corpus/samples/draft-ok.md
python3 .claude/skills/corrector/scripts/lint.py voice/corpus/samples/draft-slop.md

# thresholds from the corpus, with a table of justifications
python3 .claude/skills/corrector/scripts/calibrate.py voice/corpus/channel.json --report

# everything at once
./verify.sh

# studio
cd studio && npm install && npm run init && npm run dev   # http://127.0.0.1:5180
```

The skills work right after cloning if you open the folder in Claude Code:
`/write-as-author` and `/corrector`.

## Bring your own author

1. Collect your posts into `voice/corpus/channel.json`: a list of
   `{"date", "views", "text"}`. Thirty posts is enough, a hundred is better.
2. `python3 .claude/skills/corrector/scripts/calibrate.py voice/corpus/channel.json --out voice/thresholds.json --report`.
   Paste the report table into `voice/fingerprint.md`.
3. Fill in `voice/i_am_just_a_text_file.md` using `voice/_templates/`. This is the main
   file: not a style guide, but a description of a person from which the style follows.
4. `voice/author.json` for name, handle, platforms. `voice/registers/` for what each
   platform changes on top of the canon.
5. Run `./verify.sh`.

## Principles

- **Voice is a file, not a prompt.** The "I am just a text file" methodology.
- **A rule without a measurement is not a rule.** Linter thresholds and platform
  registers stand on counted corpora, not on opinions about good writing.
- **The tool is calibrated to the author, not to an ideal.** If the linter flags the
  author's own live text, the threshold is wrong.
- **The robot doesn't write posts.** Collectors bring an angle; a human writes, or a skill
  does on request.
- **A human publishes.** The studio and the skills hand over text; the author presses the button.

## Layout

| Folder | What's there |
|---|---|
| `voice/` | Author data: canon, registers, corpus, thresholds, fingerprint. `_templates/` are empty skeletons |
| `.claude/skills/` | `write-as-author`, `corrector` (with `lint.py`, `calibrate.py`, tests) |
| `content/` | Studio data; format in `content/README.md` |
| `studio/` | Next.js UI, see `studio/README.md` |
| `tools/` | `trend-watch`, `voice-mine`, `platform-lab`, `threads-lab` |
| `docs/` | `method.md`, `boundaries.md`, `pitfalls.md` (Russian) |
| `export/` | The scripts this repo is built with from a private workshop |

## Where it comes from

This repository is a public mirror of one author's private workshop. It is assembled by
`export/export.py` from an allowlist with a stoplist, so the private part (a real person's
canon, their messages, other people's posts from measurements) never gets here by
construction. The export tooling is included so you can keep yours the same way: private
in one repo, public in another.

How the whole thing works, with numbers and the seams that don't hold - the talk deck
from 4 September 2026: **https://hegai.net/p/kontent-zavod** (27 slides, in Russian).

MIT license.
