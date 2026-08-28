#!/usr/bin/env python3
"""Search Wikimedia Commons for plant photos and download them.

Usage:
  find_photo.py search "Aconitum napellus" [--limit 10]
  find_photo.py fetch <url-or-File:title> <output-path>
  find_photo.py credits <mapping.csv> <out.csv>

'search' prints numbered candidates with dimensions, license and URLs
(--limit is capped at 50, the API's per-request page maximum).
'fetch' downloads an image URL (or resolves a File:title to its 1400 px
rendering) to output-path, verifying the payload is a real image and
downscaling large images to 1600 px.
'credits' resolves the Commons File:titles of a mapping CSV into full
attributions (author, license, file-page URL).

Requires Pillow (Debian: python3-pil, PyPI: pillow) for image verification
and downscaling.
"""

import argparse
import csv
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, cast

try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on the environment
    sys.exit("error: Pillow is required for the fetch command "
             "(Debian: python3-pil, PyPI: pillow)")

UA = {"User-Agent": "plant-flashcards/1.0 (personal study cards; local script)"}
API = "https://commons.wikimedia.org/w/api.php"
MAX_EDGE_PX = 1600  # ~400 dpi at the 100 mm card print size
BATCH_TITLES = 50  # Commons API page limit for prop=imageinfo queries
RASTER_MIMES = ("image/jpeg", "image/png", "image/gif")


def _exit_on_http_error(exc: Exception) -> None:
    """Print a readable message for a failed HTTP request and exit 1."""
    if isinstance(exc, urllib.error.HTTPError):
        sys.exit(f"error: HTTP {exc.code} from {exc.url} ({exc.reason})")
    if isinstance(exc, urllib.error.URLError):
        sys.exit(f"error: request to {exc.filename or 'server'} "
                 f"failed: {exc.reason}")
    sys.exit(f"error: request failed: {exc}")


def api(params: dict[str, str], *, post: bool = False) -> dict[str, Any]:
    """Run a Commons API query (GET or POST) and return the parsed JSON.

    Exits with a readable message on HTTP/network errors and on API error
    payloads (which arrive with HTTP 200).
    """
    query = dict(params, format="json")
    body = urllib.parse.urlencode(query).encode()
    url = API if post else f"{API}?{body.decode()}"
    req = urllib.request.Request(url, data=body if post else None, headers=UA)
    # S310 is per-file-ignored: the tool fetches user-picked URLs only
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError) as exc:
        _exit_on_http_error(exc)
    if "error" in payload:
        info = payload["error"].get("info", "unknown API error")
        sys.exit(f"error: Commons API: {info}")
    return cast("dict[str, Any]", payload)


def imageinfo(title: str) -> dict[str, Any]:
    """Return the imageinfo block for one Commons file title."""
    data = api({
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName",
        "iiurlwidth": "1400",
    })
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))
    imageinfo_list = page.get("imageinfo") or [{}]
    return cast("dict[str, Any]", imageinfo_list[0])


def mime_ext(mime_or_url: str) -> str:
    """Guess a file extension from a MIME type or URL string."""
    lowered = (mime_or_url or "").lower()
    if "png" in lowered:
        return ".png"
    if "gif" in lowered:
        return ".gif"
    return ".jpg"


def cmd_search(args: argparse.Namespace) -> None:
    """Print numbered Commons candidates for the query."""
    limit = min(args.limit, BATCH_TITLES)  # API max: 50 pages per request
    data = api({
        "action": "query",
        "generator": "search",
        "gsrsearch": args.query + " filetype:bitmap",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName",
        "iiurlwidth": "1400",
    })
    pages = data.get("query", {}).get("pages", {})
    results = sorted(pages.values(), key=lambda page: page.get("index", 99))
    if not results:
        print("NO RESULTS", file=sys.stderr)
        sys.exit(1)
    for number, page in enumerate(results, 1):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = meta.get("LicenseShortName", {}).get("value", "?")
        print(f"[{number}] {page.get('title', '?')}")
        print(f"    {info.get('width', '?')}x{info.get('height', '?')}  "
              f"{info.get('mime', '?')}  license: {license_name}")
        print(f"    thumb: {info.get('thumburl', '')}")
        print(f"    orig:  {info.get('url', '')}")
    if len(results) < limit:
        return
    print(f"(showing all {limit} results the API returns per request)")


def save_bytes(data: bytes, out: Path) -> None:
    """Write downloaded bytes to *out* and downscale oversized images."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    downscale(out)
    print(f"saved {len(data)} bytes -> {out}")


def downscale(path: Path, max_edge: int = MAX_EDGE_PX) -> None:
    """Shrink images larger than max_edge (repo/PDF weight stays sane)."""
    with Image.open(path) as img:
        if max(img.size) <= max_edge:
            return
        img.thumbnail((max_edge, max_edge))
        img.convert("RGB").save(path, quality=88)
        print(f"downscaled to {img.size[0]}x{img.size[1]}")


def _download_image(url: str, out: Path) -> None:
    """Download *url*, verify it is a real image, then move it into place.

    The payload lands in a .part file first: a soft-404 HTML page or a
    truncated body must not end up named like an image in the deck.
    """
    req = urllib.request.Request(url, headers=UA)
    # S310 is per-file-ignored: the tool fetches user-picked image URLs only
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError) as exc:
        _exit_on_http_error(exc)
    part = out.with_name(out.name + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(data)
    try:
        with Image.open(part) as img:
            img.verify()
    except Exception as exc:  # noqa: BLE001 - PIL raises assorted types
        part.unlink(missing_ok=True)
        sys.exit(f"error: {url} is not a valid image ({exc})")
    part.replace(out)
    downscale(out)
    print(f"saved {len(data)} bytes -> {out}")


def cmd_fetch(args: argparse.Namespace) -> None:
    """Resolve the source and download it to the requested output path."""
    source = args.source
    # "File:<title>" references a Commons file; "file://" is a local URL and
    # goes to the plain-download branch (urllib handles that scheme itself)
    is_commons_title = (source.lower().startswith("file:")
                        and not source.lower().startswith("file://"))
    if is_commons_title:
        info = imageinfo(args.source)
        mime = str(info.get("mime", ""))
        if mime not in RASTER_MIMES:
            sys.exit(f"error: {args.source} is {mime or 'an unknown type'} - "
                     f"only {'/'.join(RASTER_MIMES)} files are supported")
        url = str(info.get("thumburl") or info.get("url") or "")
        if not url:
            sys.exit(f"error: no downloadable URL for {args.source}")
    else:
        url = args.source
    out = Path(args.output)
    if out.suffix.lower() not in (".jpg", ".jpeg", ".png", ".gif"):
        out = out.parent / (out.name + mime_ext(url))
    _download_image(url, out)


def strip_tags(text: str) -> str:
    """Remove HTML markup and decode entities in an extmetadata value."""
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read a CSV into row dicts, returning the header names alongside."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            sys.exit(f"error: {path} is empty (no header row)")
        return list(reader), list(reader.fieldnames)


def _resolve_batch(chunk: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Resolve one batch of File:titles via the Commons API (POST)."""
    titles = "|".join(row["title"].strip() for row in chunk)
    data = api({
        "action": "query",
        "titles": titles,
        "prop": "imageinfo",
        "iiprop": "extmetadata|url",
        "iiextmetadatafilter": "Artist|LicenseShortName",
    }, post=True)
    by_title: dict[str, dict[str, str]] = {}
    for page in data.get("query", {}).get("pages", {}).values():
        if page.get("missing") is not None:
            continue  # missing pages must not overwrite with blanks
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        by_title[page.get("title", "")] = {
            "author": strip_tags(meta.get("Artist", {}).get("value", "")),
            "license": meta.get("LicenseShortName", {}).get("value", "?"),
            "url": info.get("descriptionurl", ""),
        }
    # the API normalizes titles (underscores, capitalization); honor it
    for entry in data.get("query", {}).get("normalized", []):
        canonical = by_title.get(entry.get("to", ""))
        if canonical is not None:
            by_title[entry.get("from", "")] = canonical
    return by_title


def _resolve_credits(commons: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Resolve File:titles via the Commons API, in POST batches.

    Exits non-zero if any row resolves to an empty author: attribution is a
    deliverable of this project, not decoration.
    """
    resolved: dict[str, dict[str, str]] = {}
    for start in range(0, len(commons), BATCH_TITLES):
        chunk = commons[start:start + BATCH_TITLES]
        by_title = _resolve_batch(chunk)
        for row in chunk:
            title = row["title"].strip()
            # the canonical page title uses spaces; normalized.from keeps
            # whatever the caller passed (underscores, capitalization)
            info = next((by_title[variant] for variant in
                         (title, title.replace("_", " "))
                         if variant in by_title), None)
            if info is None:
                sys.exit(f"error: no Commons page found for {row['title']} - "
                         "fix credits_sources.csv")
            if not info["author"].strip():
                sys.exit(f"error: empty author resolved for {row['title']} - "
                         "fix credits_sources.csv")
            resolved[row["image"]] = info
    return resolved


def cmd_credits(args: argparse.Namespace) -> None:
    """Build a credits CSV from a mapping CSV.

    Mapping columns: image,title,author,license,url.  'title' is a Commons
    File:title whose author/license/source the Commons API resolves; rows
    without a title pass their fields through directly (non-Commons photos).
    """
    rows, fieldnames = read_rows(Path(args.mapping))
    if "image" not in fieldnames:
        sys.exit(f"error: {args.mapping} must have an 'image' column")
    if "title" not in fieldnames:
        sys.exit(f"error: {args.mapping} must have a 'title' column "
                 "(empty for non-Commons photos)")
    commons = [row for row in rows if (row.get("title") or "").strip()]
    resolved = _resolve_credits(commons)
    for row in rows:
        if (row.get("title") or "").strip():
            continue
        author = (row.get("author") or "").strip()
        license_name = (row.get("license") or "").strip()
        if not author and not license_name:
            print(f"warning: pass-through row {row.get('image', '?')} has no "
                  "author/license - it will show as unknown on the credits "
                  "page", file=sys.stderr)
        resolved[row["image"]] = {
            "author": author,
            "license": license_name,
            "url": (row.get("url") or "").strip(),
        }
    with Path(args.out).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image", "author", "license", "url"])
        for image in sorted(resolved):
            info = resolved[image]
            writer.writerow([image, info["author"], info["license"],
                             info["url"]])
    print(f"credits written: {args.out} ({len(resolved)} entries)")


def main() -> None:
    """Parse arguments and dispatch to the requested subcommand."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    search = sub.add_parser("search", help="search Commons for photos")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10,
                        help="candidates to list (max 50 per API request)")
    search.set_defaults(func=cmd_search)
    fetch = sub.add_parser("fetch", help="download one image")
    fetch.add_argument("source", help="image URL or File:title")
    fetch.add_argument("output")
    fetch.set_defaults(func=cmd_fetch)
    credits_parser = sub.add_parser("credits",
                                    help="build credits.csv from mapping")
    credits_parser.add_argument("mapping")
    credits_parser.add_argument("out")
    credits_parser.set_defaults(func=cmd_credits)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
