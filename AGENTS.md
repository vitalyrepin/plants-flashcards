# AGENTS.md

Instructions for coding agents working in this repository.

## What this is

A plant flashcard generator: **one deck folder = one `plants.csv` = one PDF**.
Typesetting is pdflatex + elzcards (A4, 2 × 3 cards of 105 × 99 mm, duplex:
odd pages = photos, even pages = Latin/Finnish/Russian captions mirrored for
"flip on long edge"). Photos are third-party CC-licensed works — attribution
is part of the deliverable.

## Build

Prefer the Makefile targets — `make build` (every deck), `make lint`
(ruff + mypy, the same gates CI runs), `make clean` / `make clean_all`.
The underlying commands, if you need them directly:

```console
./make_flashcards.py <deck>            # <deck> = folder with plants.csv
./make_flashcards.py --all             # build every deck found
./make_flashcards.py <deck> --clean    # remove generated files, keep the PDF
./make_flashcards.py <deck> --clean-all  # also remove the built PDF
./find_photo.py search "<latin name>"  # Wikimedia Commons search
./find_photo.py fetch <url> <file>     # download (auto-downscales to 1600 px)
./find_photo.py credits <in> <out>     # regenerate attribution CSV
```

The build fails (non-zero) on missing images, pdflatex errors, and any
Overfull/Missing-character warnings, and it removes aux/log/out files at the
end — do not commit or restore them.

## Contributing

Changes go through pull requests and must pass `make lint` — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the full developer workflow (setup,
gates, rebuild-and-inspect checklist) and the photo policy that the skills
enforce.

## Rules

- **One deck = one folder**: `<deck>/plants.csv`, `<deck>/images/`,
  `<deck>/credits_sources.csv` (curated) and `<deck>/credits.csv` (generated).
- **Photos must be freely licensed** (CC/PD). Record every photo in
  `credits_sources.csv`, and verify visually that it actually shows the plant.
  Plant names arrive in any language — resolve Latin/Finnish/Russian against
  laji.fi / Wikipedia / Wikidata, never guess.
- **Do not commit** aux/log/out artifacts; the build deletes them.
- The generated PDF's last page is the attribution page — regenerate
  `credits.csv` after any photo change so it stays in sync.

## Workflows

Step-by-step agent workflows live in `.claude/skills/` — read the relevant one
before doing deck work:

- [`.claude/skills/new-deck/SKILL.md`](.claude/skills/new-deck/SKILL.md) —
  creating a brand-new deck (scaffold, name resolution in FI/RU/Latin, photo
  search and verification, placement, credits, build, render-and-inspect
  checklist).
- [`.claude/skills/plant-cards/SKILL.md`](.claude/skills/plant-cards/SKILL.md) —
  adding plants to an existing deck, plus hard-won LaTeX gotchas (duplex
  mirroring, T2A/Cyrillic, elzcards verso quirks, `\url` vs `%`) that must
  not be "fixed" away.
