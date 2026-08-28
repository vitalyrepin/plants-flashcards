#!/usr/bin/env python3
"""Generate duplex A4 plant flashcards (photos front, names back) as PDF.

One deck = one folder = one CSV = one PDF. A deck folder contains
plants.csv (columns: latin,finnish,russian,image[,position]), an images/
subfolder and optional credits CSVs; the generator validates that each image
exists, writes <deck>.tex with elzcards (2 columns x 3 rows of 105x99 mm
cards) and compiles it to <deck>.pdf with pdflatex.

Rows go to sheets in CSV order, 6 per sheet: sheet 1 = page 1 (photos) + page 2
(captions), sheet 2 = pages 3-4, ... A row with latin '---' forces a new sheet.
The optional `position` column pins a plant to a grid cell (1-6, row-major:
1=(0,0) 2=(0,1) 3=(1,0) 4=(1,1) 5=(2,0) 6=(2,1)); rows without it auto-fill in
FILL_ORDER (top-right corner last). The caption page mirrors the front placement
for duplex printing: --duplex long (default) pairs back cell (r,c) with front
cell (r,1-c) [flip on long edge]; --duplex short pairs it with (2-r,c)
[flip on short edge].

If the deck has a credits.csv (generated from credits_sources.csv with
find_photo.py credits), a final image-credits page (attribution, license,
source link per photo) is appended; it is not part of the cards.

Usage:
  make_flashcards.py [DECK] [--duplex long|short] [--pdf-author NAME]
  make_flashcards.py --all                              # build every deck
  make_flashcards.py DECK --clean                       # remove generated
      files, keep the PDF
  make_flashcards.py --all --clean-all                  # clean every deck,
      also removing the built PDFs

DECK is a deck folder containing plants.csv - either a name relative to this
script's folder (e.g. "perennier") or a path. With no argument and exactly one
deck exists, that deck is used; with several, they are listed (or pass --all).
"""

import argparse
import csv
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

CARD_W_MM: Final = 105  # 2 x CARD_W_MM = A4 width (210 mm)
CARD_H_MM: Final = 99  # 3 x CARD_H_MM = A4 height (297 mm)
PAPER_W_MM: Final = 2 * CARD_W_MM
PAPER_H_MM: Final = 3 * CARD_H_MM
CARDS_PER_SHEET: Final = 6
FILL_ORDER: Final = (1, 3, 4, 5, 6, 2)  # grid cells (1-based, row-major)
# Longest displayed name (in characters) per font-size step; the steps keep
# even the longest binomial inside the 105 mm card width.
SIZE_LARGE_MAX_CHARS: Final = 22
SIZE_MEDIUM_MAX_CHARS: Final = 30
LATEX_ARTIFACTS = ("*.aux", "*.log", "*.out")

# __CARD_W__, __CARD_H__, __PAPER_W__, __PAPER_H__, __CARD_H2__,
# __LAST_CARD_PAGE__ and __PDF_AUTHOR__ are substituted in build_tex().
PREAMBLE_TEMPLATE = r"""\documentclass[a4paper,12pt]{article}
\usepackage[a4paper,margin=0pt]{geometry}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{graphicx}
\usepackage{eso-pic}
\usepackage{tikz}
\usepackage{multicol}
\usepackage{xurl}
% elzcards must come AFTER tikz: it re-reads the .aux at load time (cheap
% insurance -- only tikz "remember picture" would put pgf marks in the .aux,
% and this document no longer uses it)
\usepackage{elzcards}
\usepackage[colorlinks=true,urlcolor=blue]{hyperref}
\hypersetup{
  pdftitle={Plant flashcards: Latin / Finnish / Russian},
  pdfsubject={Duplex A4 printable plant memory cards},
  pdfkeywords={flashcards, plants, perennials, Finnish, Russian, Latin},
  pdfauthor={__PDF_AUTHOR__},
  pdfcreator={make\_flashcards.py (elzcards + pdflatex)}}

% Dashed black cut lines on the card pages only (not on the credits page).
% eso-pic anchors the box at the page's lower-left corner, so plain mm
% coordinates suffice (no "remember picture" / .aux coupling).
\AddToShipoutPictureFG{%
  \ifnum\value{page}<__LAST_CARD_PAGE__%
  \begin{tikzpicture}[overlay,x=1mm,y=1mm]
    \draw[line width=0.4pt,black,dash pattern=on 2mm off 1.5mm]
      (0,0) rectangle (__PAPER_W__,__PAPER_H__);
    \draw[line width=0.4pt,black,dash pattern=on 2mm off 1.5mm]
      (__CARD_W__,0) -- (__CARD_W__,__PAPER_H__);
    \draw[line width=0.4pt,black,dash pattern=on 2mm off 1.5mm]
      (0,__CARD_H__) -- (__PAPER_W__,__CARD_H__);
    \draw[line width=0.4pt,black,dash pattern=on 2mm off 1.5mm]
      (0,__CARD_H2__) -- (__PAPER_W__,__CARD_H2__);
  \end{tikzpicture}%
  \fi}

\begin{document}
"""

CARD_BLOCK_TEMPLATE = r"""\ICdim{__CARD_W__mm}{__CARD_H__mm}
"""


@dataclass(frozen=True)
class Plant:
    """One row of the deck CSV."""

    latin: str
    finnish: str = ""
    russian: str = ""
    image: str = ""
    position: int | None = None


@dataclass(frozen=True)
class PhotoCredit:
    """Attribution for one photo, as resolved from the credits CSV."""

    author: str
    license: str
    url: str


# NOTE: "{" and "}" must be escaped before "\\": the replacement for a
# literal backslash emits braces, and those must survive untouched.
LATEX_ESCAPES: Final = {
    "{": r"\{",
    "}": r"\}",
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "$": r"\$",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "©": r"\textcopyright{}",
    "×": r"$\times$",  # noqa: RUF001
    "\u2018": r"\textquoteleft{}",
    "\u2019": r"\textquoteright{}",
    "\u2013": r"\textendash{}",
    "\u2014": r"\textemdash{}",
    "\u201c": r"\textquotedblleft{}",
    "\u201d": r"\textquotedblright{}",
    "\u201e": r"\textquotedblleft{}",
}

ALLOWED_NON_ASCII: Final = re.compile(r"[^\x00-\x7F\u00A0-\u024F\u0400-\u04FF]")


def latex_escape(text: str) -> str:
    r"""Escape LaTeX special characters in plant display names.

    Paired ASCII apostrophes (cultivar names like 'Atropurpurea') become
    proper left/right single quotes via T2A text symbols.  Unknown
    non-Latin/Cyrillic characters abort the build with a clear message
    instead of a pdflatex traceback.
    """
    for char, replacement in LATEX_ESCAPES.items():
        text = text.replace(char, replacement)
    bad = ALLOWED_NON_ASCII.search(text)
    if bad:
        sys.exit(f"error: unsupported character {bad.group(0)!r} in {text!r} - "
                 "add a mapping to latex_escape()")
    return text


def capitalize(name: str) -> str:
    """Return *name* with its first letter capitalised for display."""
    return name[:1].upper() + name[1:] if name else name


def font_size(texts: Sequence[str]) -> str:
    """Pick a font size command so the longest name fits a 105 mm card."""
    longest = max(len(text) for text in texts)
    if longest <= SIZE_LARGE_MAX_CHARS:
        return r"\LARGE"
    if longest <= SIZE_MEDIUM_MAX_CHARS:
        return r"\Large"
    return r"\large"


def href_url(url: str) -> str:
    r"""Escape a URL for \href's first argument.

    % and # would otherwise act as comment/parameter characters while the
    argument is scanned.
    """
    return url.replace("%", r"\%").replace("#", r"\#")


def card_front(image_rel: str, url: str = "") -> str:
    """Typeset the photo side of one card, hyperlinked to its source page."""
    image = (r"\includegraphics[width=100mm,height=93mm,keepaspectratio]{"
             + image_rel + "}")
    if url:
        # clicking a photo opens its source page
        image = "\\href{" + href_url(url) + "}{" + image + "}"
    return r"\parbox[c][95mm][c]{103mm}{\centering%" + "\n" + image + "}"


def card_back(latin: str, finnish: str, russian: str) -> str:
    """Typeset the caption side of one card (three lines, B&W)."""
    size = font_size((latin, finnish, russian))
    lines = ["{" + size + " " + latex_escape(latin) + r"}\\[5mm]"]
    if finnish:
        lines.append("{" + size + " "
                     + latex_escape(capitalize(finnish)) + r"}\\[5mm]")
    if russian:
        lines.append("{" + size + " "
                     + latex_escape(capitalize(russian)) + r"\par}")
    body = "\n".join(lines)
    return "\\parbox[c][95mm][c]{103mm}{\\centering%\n" + body + "}"


def _plant_from_row(row: dict[str, str], rowno: int, csv_path: Path
                    ) -> Plant:
    """Build a Plant from one CSV row, validating the position value."""
    position = (row.get("position") or "").strip()
    if position and position not in tuple(str(n) for n in range(1, 7)):
        sys.exit(f"error: {csv_path} line {rowno}: position must be "
                 "1-6 or empty")
    return Plant(
        latin=(row.get("latin") or "").strip(),
        finnish=(row.get("finnish") or "").strip(),
        russian=(row.get("russian") or "").strip(),
        image=(row.get("image") or "").strip(),
        position=int(position) if position else None,
    )


def read_plants(csv_path: Path, images_dir: Path) -> list[list[Plant]]:
    """Read the deck CSV into sheet groups (a '---' row forces a new group).

    Also validates that every referenced image exists and that positions are
    unique within each sheet group.
    """
    sheets: list[list[Plant]] = [[]]
    taken: dict[int, str] = {}  # position -> latin, per current sheet group
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for rowno, row in enumerate(csv.DictReader(handle), start=2):
            latin = (row.get("latin") or "").strip()
            if not latin:
                continue
            if latin == "---":
                if sheets[-1]:
                    sheets.append([])
                    taken.clear()
                continue
            plant = _plant_from_row(row, rowno, csv_path)
            if plant.position is not None and plant.position in taken:
                sys.exit(f"error: {csv_path} line {rowno}: position "
                         f"{plant.position} used by both "
                         f"'{taken[plant.position]}' and '{plant.latin}'")
            if plant.position is not None:
                taken[plant.position] = plant.latin
            sheets[-1].append(plant)
    plants = [plant for sheet in sheets for plant in sheet]
    if not plants:
        sys.exit(f"error: no plants found in {csv_path}")
    _require_images(plants, images_dir)
    return sheets


def _require_images(plants: list[Plant], images_dir: Path) -> None:
    """Exit with a clear message if any referenced image is missing."""
    missing = [plant.image for plant in plants
               if plant.image and not (images_dir / plant.image).is_file()]
    unnamed = [plant.latin for plant in plants if not plant.image]
    if unnamed:
        missing.append("(row with empty image field: "
                       + ", ".join(unnamed) + ")")
    if missing:
        sys.exit("error: missing image file(s):\n  " + "\n  ".join(missing))


def assign_sheet(sheet_rows: list[Plant]) -> list[Plant | None]:
    """Place one sheet's rows on the 2x3 grid, honouring explicit positions.

    Position conflicts across the whole sheet group are already rejected by
    read_plants; this only distributes the rows.
    """
    grid: list[Plant | None] = [None] * 6
    for row in sheet_rows:
        if row.position is not None:
            grid[row.position - 1] = row
    for row in sheet_rows:
        if row.position is None:
            for cell_no in FILL_ORDER:
                if grid[cell_no - 1] is None:
                    grid[cell_no - 1] = row
                    break
    return grid


def split_sheets(sheets: list[list[Plant]]) -> list[list[Plant | None]]:
    """Chunk every sheet group into grids of CARDS_PER_SHEET placements."""
    grids: list[list[Plant | None]] = []
    for sheet in sheets:
        grids.extend(assign_sheet(sheet[start:start + CARDS_PER_SHEET])
                     for start in range(0, len(sheet), CARDS_PER_SHEET))
    return grids


def credits_page(plants: list[Plant],
                 credits_map: dict[str, PhotoCredit]) -> str:
    """Typeset the attribution page (regular margins, tiny clickable links)."""
    heading = ('Image credits --- Kuvien l\\"ahteet --- '
               'Источники изображений')
    lines = ["\\clearpage\n\\newgeometry{margin=20mm}\n\\thispagestyle{empty}\n",
             "\\begin{center}{\\small\\bfseries " + heading
             + "}\\end{center}\n"
             "\\vspace{2mm}\n\\begin{multicols}{2}\\tiny\\raggedright\n"
             "\\hyphenpenalty=10000 \\exhyphenpenalty=10000\n"]
    seen: set[str] = set()
    for plant in plants:
        if plant.image in seen:
            continue
        seen.add(plant.image)
        entry = "\\textbf{" + latex_escape(plant.latin) + "} --- "
        credit = credits_map.get(plant.image)
        if credit is not None:
            entry += (latex_escape(credit.author.rstrip(".").strip()) + ". "
                      + latex_escape(credit.license) + ". "
                      + "\\url{" + credit.url + "}")
        else:
            entry += "No credit information recorded --- see credits.csv."
        lines.append(entry + "\n\\par\\smallskip\n")
    lines.append("\\end{multicols}\n\\vfill\n"
                 "\\begin{center}\\tiny "
                 "Nursery photos are reproduced for personal use only. "
                 "This page is for information only and is not part of the "
                 "cards.\\end{center}\n\\restoregeometry\n")
    return "\n".join(lines)


def build_tex(sheets: list[list[Plant]],
              credits_map: dict[str, PhotoCredit], duplex: str,
              pdf_author: str) -> tuple[str, int]:
    """Generate the full LaTeX document and return it with the sheet count."""
    base = (f"columns=2,rows=3,hsize={CARD_W_MM}mm,vsize={CARD_H_MM}mm,"
            "hgap=0mm,vgap=0mm,no marks")
    grids = split_sheets(sheets)
    n_sheets = len(grids)
    substitutions = {
        "__CARD_H2__": str(2 * CARD_H_MM),  # keep before __CARD_H__
        "__CARD_W__": str(CARD_W_MM),
        "__CARD_H__": str(CARD_H_MM),
        "__PAPER_W__": str(PAPER_W_MM),
        "__PAPER_H__": str(PAPER_H_MM),
        "__LAST_CARD_PAGE__": str(2 * n_sheets + 1),
        "__PDF_AUTHOR__": latex_escape(pdf_author),
    }
    preamble = PREAMBLE_TEMPLATE
    for token, value in substitutions.items():
        preamble = preamble.replace(token, value)
    card_block = (CARD_BLOCK_TEMPLATE
                  .replace("__CARD_W__", str(CARD_W_MM))
                  .replace("__CARD_H__", str(CARD_H_MM)))
    parts: list[str] = [preamble, card_block]
    for grid in grids:
        parts.extend(_front_tex(slot, credits_map) for slot in grid)
        parts.append("\\MakeIC[" + base + "]\n")
        if duplex == "long":
            order = [row * 2 + (1 - col) + 1
                     for row in range(3) for col in range(2)]
        else:
            order = [(2 - row) * 2 + col + 1
                     for row in range(3) for col in range(2)]
        parts.extend(_back_tex(slot) for slot in grid)
        parts.append("\\MakeIC[" + base + ",order={"
                     + " ".join(map(str, order)) + "}]\n")
    all_plants = [plant for sheet in sheets for plant in sheet]
    parts.append(credits_page(all_plants, credits_map) if credits_map else "")
    parts.append("\\end{document}\n")
    return "".join(parts), n_sheets


def _front_tex(slot: Plant | None,
               credits_map: dict[str, PhotoCredit]) -> str:
    """Typeset one photo card; empty cells emit an empty card definition."""
    content = r"\mbox{}"
    if slot is not None:
        credit = credits_map.get(slot.image)
        url = credit.url if credit is not None else ""
        content = card_front("images/" + slot.image, url)
    return "\\IndexCard{%\n" + content + "\n}\n"


def _back_tex(slot: Plant | None) -> str:
    """Typeset one caption card; empty cells emit an empty card definition."""
    content = r"\mbox{}"
    if slot is not None:
        content = card_back(slot.latin, slot.finnish, slot.russian)
    return "\\IndexCard{%\n" + content + "\n}\n"


def _run_tool(cmd: list[str], cwd: Path | None = None, hint: str = ""
              ) -> subprocess.CompletedProcess[str]:
    """Run a build tool, exiting with a friendly message if it is missing."""
    try:
        # S603 suppressed: arguments are built from local paths only
        return subprocess.run(cmd, cwd=cwd, capture_output=True,  # noqa: S603
                              encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, check=False,
                              shell=False)
    except FileNotFoundError:
        sys.exit(f"error: '{cmd[0]}' not found"
                 + (f" - {hint}" if hint else ""))


def compile_pdf(tex_path: Path) -> Path:
    """Run pdflatex twice, verify the log, and clean LaTeX artifacts."""
    for _ in range(2):  # two runs: elzcards re-reads the .aux from the first
        result = _run_tool(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             tex_path.name],
            cwd=tex_path.parent, hint="install texlive-latex-base")
        if result.returncode != 0:
            tail = "\n".join(result.stdout.splitlines()[-25:])
            sys.exit(f"error: pdflatex failed:\n{tail}")
    log_path = tex_path.with_suffix(".log")
    if not log_path.is_file():
        sys.exit("error: pdflatex reported success but wrote no log file - "
                 "is another build of this deck running?")
    log = log_path.read_text(encoding="utf-8", errors="replace")
    problems = [line for line in log.splitlines()
                if line.startswith(("Overfull \\hbox", "Missing character"))]
    if problems:
        shown = "\n".join(problems[:10])
        sys.exit(f"error: typesetting problems detected:\n{shown}\n"
                 f"({len(problems)} total - fix the source data or layout)")
    pdf_path = tex_path.with_suffix(".pdf")
    for suffix in (".aux", ".log", ".out"):  # keep the deck folder clean
        artifact = tex_path.with_suffix(suffix)
        try:
            artifact.unlink(missing_ok=True)
        except OSError as exc:
            sys.exit(f"error: cannot remove {artifact}: {exc}")
    return pdf_path


def clean_deck(deck: Path, *, remove_pdf: bool) -> None:
    """Remove a deck's generated files (the script knows their names).

    Removes the .tex, LaTeX artifacts and preview renders; with
    remove_pdf also the built <deck>.pdf.
    """
    patterns = ["*.tex", "*.aux", "*.log", "*.out",
                "preview-*.png", "measure-*.png"]
    if remove_pdf:
        patterns.append("*.pdf")
    removed = 0
    for pattern in patterns:
        for artifact in deck.glob(pattern):
            try:
                artifact.unlink(missing_ok=True)
                removed += 1
            except OSError as exc:
                sys.exit(f"error: cannot remove {artifact}: {exc}")
    print(f"cleaned {deck} ({removed} files)")


def _single_deck(script_dir: Path, name: str) -> Path:
    """Resolve one explicitly named deck folder."""
    deck = Path(name)
    if not deck.is_absolute() and not deck.is_dir():
        candidate = script_dir / deck
        if candidate.is_dir():
            deck = candidate
    if not deck.is_dir():
        sys.exit(f"error: deck folder '{deck}' not found")
    deck = deck.resolve()
    if not deck.name:
        sys.exit("error: pass the deck as a named folder, not '.'")
    return deck


def _resolve_decks(script_dir: Path, name: str | None, *,
                   all_decks: bool) -> list[Path]:
    """Return the deck folders the command should operate on."""
    decks = sorted(placement.parent for placement
                   in script_dir.glob("*/plants.csv"))
    if all_decks:
        if not decks:
            sys.exit("error: no deck folders found - each deck needs "
                     "plants.csv + images/ next to this script")
        return decks
    if name is not None:
        return [_single_deck(script_dir, name)]
    if len(decks) == 1:
        return decks
    if not decks:
        sys.exit("error: no deck folders found - each deck needs "
                 "plants.csv + images/ next to this script")
    names = "\n  ".join(placement.name for placement in decks)
    sys.exit("error: several decks found - pass one as an "
             f"argument:\n  {names}")


def _read_credits(deck: Path) -> dict[str, PhotoCredit]:
    """Read the generated credits CSV of a deck, if present."""
    credits_path = deck / "credits.csv"
    if not credits_path.is_file():
        return {}
    with credits_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "image" not in reader.fieldnames:
            sys.exit(f"error: {credits_path} must have an 'image' column")
        return {row["image"]: PhotoCredit(
            author=row.get("author") or "",
            license=row.get("license") or "",
            url=row.get("url") or "",
        ) for row in reader}


def _lock_deck(deck: Path) -> Path:
    """Take an exclusive per-deck build lock (guards parallel builds)."""
    lock = deck / ".build.lock"
    try:
        with lock.open("x") as handle:
            handle.write("build in progress\n")
    except FileExistsError:
        sys.exit(f"error: {lock} exists - another build of this deck may be "
                 "running; delete the file if that is not the case")
    return lock


def _build_deck(deck: Path, duplex: str, pdf_author: str) -> tuple[int, int]:
    """Build one deck; return (plant count, pdf page count)."""
    csv_path = deck / "plants.csv"
    images_dir = deck / "images"
    if not csv_path.is_file():
        sys.exit(f"error: {csv_path} not found")

    sheets = read_plants(csv_path, images_dir)
    plants = [plant for sheet in sheets for plant in sheet]
    tex_path = deck / f"{deck.name}.tex"
    tex, n_sheets = build_tex(sheets, _read_credits(deck),
                              duplex, pdf_author)
    tex_path.write_text(tex, encoding="utf-8")
    pdf_path = compile_pdf(tex_path)

    info = _run_tool(["pdfinfo", str(pdf_path)],
                     hint="install poppler-utils")
    pages = "?"
    if info.returncode == 0:
        pages = next((line.split()[-1] for line in info.stdout.splitlines()
                      if line.startswith("Pages:")), "?")
    else:
        print("warning: pdfinfo not available - page count unknown",
              file=sys.stderr)
    print(f"deck: {deck.name}  plants: {len(plants)}  sheets: {n_sheets}  "
          f"pdf pages: {pages}")
    print(f"written: {pdf_path}")
    return len(plants), n_sheets


def main() -> None:
    """Parse arguments and build or clean the requested decks."""
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck", nargs="?",
                        help="deck folder containing plants.csv and images/ - "
                             "a name relative to this script's folder (e.g. "
                             "'perennier') or a path; optional when there is "
                             "exactly one deck")
    parser.add_argument("--all", action="store_true",
                        help="apply to every deck found")
    parser.add_argument("--duplex", choices=("long", "short"), default="long",
                        help="printer duplex flip edge (default: long)")
    parser.add_argument("--pdf-author", default="",
                        help="author name stored in the PDF metadata")
    parser.add_argument("--clean", action="store_true",
                        help="remove the deck's generated files "
                             "(.tex, LaTeX artifacts, previews; keep the PDF)")
    parser.add_argument("--clean-all", action="store_true",
                        help="like --clean, but also remove the built PDF")
    args = parser.parse_args()
    if args.clean and args.clean_all:
        sys.exit("error: --clean and --clean-all are mutually exclusive")

    decks = _resolve_decks(script_dir, args.deck, all_decks=args.all)
    if args.clean or args.clean_all:
        for deck in decks:
            clean_deck(deck, remove_pdf=args.clean_all)
        return
    for deck in decks:
        lock = _lock_deck(deck)
        try:
            _build_deck(deck, args.duplex, args.pdf_author)
        finally:
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
