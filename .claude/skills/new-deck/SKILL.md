---
name: new-deck
description: Create a NEW flashcard deck from scratch (new deck folder + PDF) when the user supplies plant names in any language, optionally with sheet placement (rows/cells). Use for phrases like "next sheet", "new deck", "new file with plants A, B, C". For adding plants to an EXISTING deck, use the plant-cards skill instead.
---

# Create a new flashcard deck

Execute this workflow when the user asks to create a new deck and supplies
plant names in any language, optionally with the grid placement. Existing
decks live as folders in the repo root (e.g. `perennier/`) - study one if an
example is needed. Layout and build gotchas: see the plant-cards skill.

## 1. Deck name and scaffold

- Pick a short lowercase folder name with the user if not given
  (e.g. `trees`, `perennier`). The PDF will be named after it.
- Create:

```console
mkdir -p <name>/images
```

- `<name>/plants.csv` with the header row:
  `latin,finnish,russian,image,position`
- `<name>/credits_sources.csv` with the header row:
  `image,title,author,license,url`

## 2. Placement

- The user may give rows ("row 0: A AND B, row 1: C, row 2: D"). Map rows to
  the `position` column: 1=(0,0), 2=(0,1), 3=(1,0), 4=(1,1), 5=(2,0), 6=(2,1)
  (row-major). Within a row, the first named plant takes the left cell.
- Plants without explicit placement are written WITHOUT a position value: the
  generator auto-fills each sheet in reading order
  (0,0) → (1,0) → (1,1) → (2,0) → (2,1), leaving the top-right corner last.
- A row with `---` in the latin column forces a new sheet (use it when a sheet
  has fewer than 6 plants and the next batch must start fresh).

## 3. Per plant: resolve the three names

From whatever language the user used, determine canonical Latin (+ cultivar or
Group), Finnish name and Russian name. Prefer direct API calls:

```console
curl -s "https://laji.fi/api/taxa/search?query=<finnish name>"
```
→ `scientificName` + `vernacularName.fi` (authoritative for Finnish names).

```console
curl -s "https://fi.wikipedia.org/w/api.php?action=query&titles=<Name>&prop=extracts&exintro&explaintext&format=json&formatversion=2"
```
→ the first sentence of the extract contains the Latin name.

```console
curl -s "https://www.wikidata.org/w/api.php?action=wbgetentities&sites=enwiki&titles=<Latin>&props=labels&languages=ru&format=json&formatversion=2"
```
→ Russian label. Fallbacks: ru.wikipedia article titles, nursery sites.
Surprising mappings (garden names → unexpected genera) are confirmed with the
user before the card is built. Finnish Group-cultivar convention is
"...-Ryhmä" / "... Ryhmä" (e.g. `Astilbe Arendsii-Ryhmä`).

## 4. Per plant: photo

```console
./find_photo.py search "<Latin name>"
./find_photo.py fetch <thumb-url> <name>/images/<latin-slug>.jpg
```

- `<latin-slug>` = Latin name lowercased, non-alphanumerics → `_`
  (e.g. `iris_sibirica.jpg`). Filenames are always derived from the Latin name.
- Pick a color photo showing the plant as recognizable in a garden: typical
  flowers/foliage, plant-level rather than fields, not herbarium scans, not
  B&W, no unrelated species in frame. License must be CC/PD — record it.
- Downloads are auto-downscaled to 1600 px. Fetch sequentially (parallel
  fetches hit Wikimedia rate limiting). Pillow (python3-pil) is required.
- **Always visually verify** the downloaded image (Read tool) that it shows
  the right plant with flowers visible; otherwise take the next candidate.
- Flickr photos are acceptable when the page shows a CC license (sizes:
  `_b` = 1024 px, `_h` = 1600 px sometimes 410 Gone).
- If no suitable free photo exists, tell the user and offer a look-alike
  species/cultivar or ask for their own photo.

## 5. Credits

Add one row per photo to `<name>/credits_sources.csv`:

- Commons photos: `image,title` (title = `File:...` name); author/license/url
  are fetched later from the Commons API.
- Non-Commons photos (Flickr/nursery): leave `title` empty, fill
  `author,license,url` directly; mark non-free photos
  "© ... , personal use only" (they must be replaced before publishing).

Then regenerate the attributions:

```console
./find_photo.py credits <name>/credits_sources.csv <name>/credits.csv
```

## 6. Build and verify

```console
./make_flashcards.py <name> --pdf-author "<author>"
pdftoppm -png -r 100 <name>/<name>.pdf <name>/preview
```

View every page: photos in the requested cells, captions mirrored on the even
pages (long-edge duplex: caption cell (r,c) belongs to photo cell (r,1-c)),
names spelled correctly (Cyrillic included), no typesetting problems (the
build fails on Overfull/Missing character by itself). Report the deck stats:
plants, sheets, pdf pages, and how to print (duplex, long edge, 100 % scale).
