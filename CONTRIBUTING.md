# Contributing

## Development setup

Debian/Ubuntu package names; adjust for your distribution:

```console
apt install texlive-latex-extra texlive-lang-cyrillic cm-super \
            poppler-utils python3-pil
pip install ruff==0.11.6 mypy==2.3.1 pillow
```

`cm-super` is mandatory: without it pdfTeX falls back to bitmap Cyrillic
fonts (blurry print, no copy/paste) with only a soft warning.

## Workflow

1. Create a branch for your change.
2. Make the change **using the skills** — they are the expected way to work
   on decks, not an optional shortcut. Each skill encodes the whole
   procedure: name resolution via laji.fi / Wikipedia / Wikidata, photo
   search with license checks, visual verification that the photo really
   shows the plant, credits bookkeeping, build and render check.

   - **Creating a new deck:** use the
     [`new-deck` skill](.claude/skills/new-deck/SKILL.md). In Claude Code it
     fires when you ask for "a new deck with plants …"; without Claude Code,
     read the file and follow it manually.
   - **Adding plants to an existing deck, or rebuilding one:** use the
     [`plant-cards` skill](.claude/skills/plant-cards/SKILL.md).

   Deck data still lands in plain files (`<deck>/plants.csv`,
   `credits_sources.csv`, `images/`) — the skills are the procedure, the CSVs
   are the deliverable.
3. Run the gates locally — `make lint` (or the two commands below). The CI
   pipeline (`.github/workflows/lint.yml`) runs the same checks on every
   push and pull request, and a PR is only merged when they pass:

   ```console
   make lint
   # equivalent to:
   ruff check .
   mypy make_flashcards.py find_photo.py
   ```

   The ruff rule set is `select = ["ALL"]` (see `pyproject.toml`) with a
   small documented ignore list; if you add an ignore, justify it with a
   comment like the existing ones.
4. Rebuild the affected deck and **look at the pages** before opening the PR:

   ```console
   make build
   pdftoppm -png -r 100 <deck>/<deck>.pdf <deck>/preview
   ```

   Check: photos in the requested cells, captions mirrored on the even
   pages, no content overflowing a card, credits page up to date.
5. Commit (aux/log/out files are deleted by the build and gitignored) and
   open a pull request.

## Photo policy

The photo rules below are enforced by the skills during the workflow; this is
what they boil down to:

- Only freely licensed photos (CC0, CC BY, CC BY-SA) may be committed.
  Non-free photos must never enter the repository — mark them
  "personal use only" locally and replace them before any publication.
- Every photo needs a row in the deck's `credits_sources.csv`, and
  `credits.csv` must be regenerated
  (`./find_photo.py credits …`) so the PDF's attribution page stays correct.
- The attribution page and `credits.csv` are part of the deliverable: a PR
  that adds a photo without credits is incomplete.
- Photos are third-party works: CC BY-SA's ShareAlike clause applies to the
  generated card sheets. The code license (MIT, see `LICENSE`) covers the
  scripts only.
