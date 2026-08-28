---
name: plant-cards
description: Work with flashcard decks - add plants to an existing deck (resolving names in any language, fetching CC photos), regenerate or adjust the deck PDF. Use when the user gives plant names to add to an existing deck or asks to (re)build one. For creating a brand-new deck folder, use the new-deck skill instead.
---

# Plant memory cards

Printable flashcards: A4 sheet, 2 cols × 3 rows of 105×99 mm cards. Odd pages =
color plant photos (clicking a photo opens its source page), even pages = the
same cells mirrored with Latin, Finnish and Russian names (B&W). Dashed black
cut lines on both sides. Print duplex, **flip on long edge, scale 100 %
"Actual size"** — the layout is built for that (`--duplex short` exists for
the other printers).

**Multi-deck layout** — one deck = one folder = one CSV = one PDF. The
generator and helper live in the repo root; decks are folders beside them:

```
make_flashcards.py       generator: <deck>/plants.csv → <deck>/<deck>.pdf
find_photo.py            Wikimedia Commons photo search / download / credits
perennier/               deck "perennier"
  plants.csv, images/, credits_sources.csv, credits.csv, perennier.pdf
```

## Workflow when the user gives plant names (existing deck)

1. **Resolve all three names.** From whatever language the user used, determine
   canonical Latin (+ cultivar or Group), Finnish name and Russian name.
   Prefer direct API calls over web search when the endpoints are known:
   - `curl -s "https://laji.fi/api/taxa/search?query=<finnish name>"`
     → `scientificName` + `vernacularName.fi` (authoritative for Finnish).
   - `curl -s "https://fi.wikipedia.org/w/api.php?action=query&titles=<Name>&prop=extracts&exintro&explaintext&format=json&formatversion=2"`
     → the first sentence of the extract contains the Latin name.
   - Russian labels:
     `https://www.wikidata.org/w/api.php?action=wbgetentities&sites=enwiki&titles=<Latin>&props=labels&languages=ru&format=json&formatversion=2`
   Cultivars keep their cultivar string; Finnish/Russian names are displayed
   with a capital first letter (done by the script). Finnish Group-cultivar
   convention is "...-Ryhmä" / "... Ryhmä" (e.g. `Astilbe Arendsii-Ryhmä`).
2. **Fetch a photo.** Use the helper (it searches Wikimedia Commons, shows
   license):
   `./find_photo.py search "<Latin name>"`
   Pick a clear color photo showing the plant as recognizable in a garden
   (typical flowers/foliage, plant-level rather than fields, not herbarium
   scans, not B&W, no unrelated species in frame). License must be CC/PD.
   Download (auto-downscales to 1600 px):
   `./find_photo.py fetch <thumb-url> <deck>/images/<slug>.jpg`
   where `<slug>` = Latin name lowercased, non-alphanumerics → `_`.
   Download sequentially - parallel fetches hit Wikimedia rate limiting (429).
   `find_photo.py` requires Pillow (Debian: python3-pil) for verification and
   downscaling, and fails fast with an install hint if it is missing.
   Flickr photos are acceptable when the page shows a CC license (sizes:
   `_b` = 1024 px, `_h` = 1600 px sometimes 410 Gone).
   **Always visually verify** the image (Read tool) that it shows the right
   plant with flowers visible; otherwise take the next candidate.
3. **Add a row to `<deck>/plants.csv`.** Columns:
   `latin,finnish,russian,image[,position]`. `position` (1-6, row-major) is
   optional; rows go to sheets in CSV order, 6 per sheet; a row with latin
   `---` forces a new sheet.
4. **Credits (IPR).** Every photo needs a row in `<deck>/credits_sources.csv`
   (`image,title,author,license,url`; `title` = Commons `File:...` name; for
   non-Commons photos fill author/license/url directly, marking non-free
   photos "© ... , personal use only" - they must be replaced before
   publishing). Then regenerate:
   `./find_photo.py credits <deck>/credits_sources.csv <deck>/credits.csv`
5. **Regenerate:** `./make_flashcards.py <deck>` (options: `--duplex
   long|short`, `--pdf-author NAME`). The script validates images, writes
   `<deck>/<deck>.tex` and runs pdflatex twice, failing on
   Overfull/Missing-character warnings and cleaning aux/log/out afterwards.
6. **Verify the PDF:** `pdftoppm -png -r 100 <deck>/<deck>.pdf <deck>/preview`
   then view the pages: photos on odd pages in the requested cells, captions
   on even pages mirrored (long-edge: caption cell (r,c) belongs to photo cell
   (r,1-c)), names spelled correctly (Cyrillic included), cut lines on card
   pages only.

## Gotchas (already solved, do not undo)

- `tikz`/`eso-pic` MUST be loaded BEFORE `elzcards`: elzcards re-reads the .aux
  at load time. The cut-line overlay deliberately does NOT use tikz
  `remember picture` (it would fill the .aux with `\pgfsyspdfmark` lines and
  trigger "multiply defined" warnings; eso-pic's lower-left anchor + plain mm
  coordinates are pixel-identical).
- elzcards' own two-sided `\IndexCard{front}{back}` verso layout misplaces
  cards in this setup - each sheet uses two one-sided `\MakeIC` calls, the
  caption one with an explicit `order={...}` pattern (see `build_tex`).
- pdflatex needs `[T2A]{fontenc}` for Cyrillic; the cm-super package provides
  the vector Cyrillic fonts (without it pdfTeX falls back to bitmap fonts).
  babel-russian is not required - only T2A encoding, no hyphenation needed.
  Curly cultivar quotes are emitted as `\textquoteleft`/`\textquoteright`
  (plain U+2018/19 are unmapped in T2A).
- Keep `\url` outermost for links: Commons/Flickr URLs contain `%`
  (percent-encoding), which breaks inside macro arguments. Link coloring needs
  `hyperref[colorlinks=true,urlcolor=...]` (hidelinks disables urlcolor).
- Name resolution may surprise: always verify with laji.fi/Wikipedia - e.g.
  suikeroalpi = *Lysimachia nummularia* (not a Pulmonaria), syyskaunosilmä =
  *Coreopsis verticillata* (not Boltonia).
