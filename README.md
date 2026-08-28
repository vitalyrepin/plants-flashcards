# Plant flashcards (Latin / Finnish / Russian)

Duplex-printable A4 memory cards for learning plant names: the **front** of
each card is a color photo, the **back** has the plant's name in **Latin,
Finnish and Russian**. Dashed cut lines on both sides; 6 cards per sheet
(2 × 3, each 105 × 99 mm). Built with plain **pdflatex** and the
[elzcards](https://ctan.org/pkg/elzcards) package.

Printing: **duplex ON, flip on long edge, scale "Actual size" (100 %)** —
each card's back is then exactly its own photo. (Use `--duplex short` for
printers that flip on the short edge.)

## Decks: one folder = one CSV = one PDF

Every deck lives in its own subfolder with self-contained data:

```
make_flashcards.py         generator: <deck>/plants.csv → <deck>/<deck>.pdf
find_photo.py              Wikimedia Commons photo search / download / credits
pyproject.toml             ruff + mypy settings (the CI gates)
Makefile                   make build / lint / clean / clean_all
perennier/                 example deck (40 perennials, 7 sheets)
  plants.csv               one row per plant: latin,finnish,russian,image[,position]
  images/                  one photo per plant, named from the Latin name
  credits_sources.csv      image → source mapping (Commons File:title or direct)
  credits.csv              generated: image → author, license, source URL
  perennier.tex/.pdf       generated output (PDF = print-ready)
trees/                     …next deck goes here
.claude/skills/            Claude Code workflows (new-deck, plant-cards)
.github/workflows/         CI: ruff + mypy on every push/PR
AGENTS.md                  agent instructions (any coding agent)
CLAUDE.md                  pointer to AGENTS.md for Claude Code
CONTRIBUTING.md            dev setup, PR workflow, photo policy
LICENSE                    MIT (code only — photos keep their CC licenses)
README.md                  this file
```

## Build

```console
make build                          # build every deck found
./make_flashcards.py perennier      # build one deck
./make_flashcards.py                # builds the only deck, or lists them
./make_flashcards.py perennier --pdf-author "Your Name"
```

Handy targets: `make lint` (ruff + mypy, the same gates the CI runs),
`make clean` (delegates to the generator to remove caches, LaTeX artifacts
and previews, keeping the PDFs) and `make clean_all` (also removes the built
PDFs — everything regenerates from the CSVs). The generator offers the same
cleanup directly: `./make_flashcards.py perennier --clean` / `--clean-all`.

Dependencies (Debian package names): `texlive-latex-extra` (elzcards),
`texlive-lang-cyrillic` (T2A), **`cm-super`** (vector Cyrillic Type 1 fonts —
without it pdfTeX silently falls back to blurry bitmap fonts),
`python3` + `poppler-utils` (pdfinfo), `python3-pil` (Pillow — required by
`find_photo.py` for image verification and downscaling). pdflatex is required;
the preamble does not support XeLaTeX/LuaLaTeX.

## Adding plants

1. Append a row to `<deck>/plants.csv`: `latin,finnish,russian,image`.
   Optional `position` (1-6, row-major) pins the plant to a card cell; rows
   auto-fill in reading order with the top-right corner last. A `---` row
   forces a new sheet.
2. Put a photo named after the Latin name (e.g. `iris_sibirica.jpg`) into
   `<deck>/images/`. `find_photo.py` searches Wikimedia Commons for you
   (search, download, auto-downscale) — see its `--help`.
3. Re-run the build. The last PDF page always carries the photo credits.

Contributions: see [CONTRIBUTING.md](CONTRIBUTING.md) — the CI pipeline runs
`ruff` and `mypy` on every push and pull request.

## Skills (Claude Code / agents)

Two agent skills ship with the repo in [`.claude/skills/`](.claude/skills/).
Claude Code picks them up automatically in this folder (they can also be
invoked explicitly as `/new-deck` and `/plant-cards`); [`AGENTS.md`](AGENTS.md)
describes the same workflows for any other coding agent.

| Skill | Fires when you… | What it does |
|---|---|---|
| [`new-deck`](.claude/skills/new-deck/SKILL.md) | ask to create a **new** deck/file, giving plant names (any language) and optionally rows/cells | scaffolds `<deck>/`, resolves Latin/Finnish/Russian names, fetches and verifies CC photos, writes CSVs + credits, builds and checks the PDF |
| [`plant-cards`](.claude/skills/plant-cards/SKILL.md) | give plant names for an **existing** deck, or ask to (re)build it | the same pipeline against the existing deck folder |

Full workflows, including the LaTeX gotchas (duplex mirroring, T2A/Cyrillic,
elzcards quirks), are documented inside the skill files; [`AGENTS.md`](AGENTS.md)
summarizes them for any coding agent.

## Image credits & license

Every photo is attributed on the last page of the PDF (author, license,
clickable source link) and in the machine-readable `<deck>/credits.csv`.
Photos come from [Wikimedia Commons](https://commons.wikimedia.org/) and Flickr
under CC BY / CC BY-SA / CC0 — note that **CC BY-SA's ShareAlike clause applies
to the derived card sheets**. Keep `credits_sources.csv` up to date when you
add a photo, and regenerate `credits.csv`:

```console
./find_photo.py credits perennier/credits_sources.csv perennier/credits.csv
```

## License

Two different things are licensed here — don't mix them up:

**The code** (`make_flashcards.py`, `find_photo.py`, build files, this
documentation) is licensed under the
[MIT License](LICENSE).
This license is about the **scripts only**.

**The photos** are NOT covered by it: every image keeps its own Creative
Commons license (CC BY-SA / CC BY / CC0 — see `credits.csv` or the credits
page of the PDF), and attribution is required. Because most photos are
CC BY-SA, the **generated card sheets** (`perennier.pdf` and anything printed
from it) are effectively shared under **CC BY-SA** as well.
