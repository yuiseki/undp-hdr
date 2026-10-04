#!/usr/bin/env python3
"""Fetch the data files of the current Human Development Report release.

The Human Development Report Office (UNDP) lists its downloads on
https://hdr.undp.org/data-center/documentation-and-downloads . This script
reads that page and takes every file in its "Data links" blocks: the
statistical annex tables (xlsx, one per index plus "All tables"), the MPI
tables 1 and 2 (xlsx), the composite indices time series (csv) and its
metadata (xlsx). Not taken: the report and technical-note PDFs, the
"Calculating the Indices" teaching workbook, past releases, and the
hdrdata.org API (it needs a key).

The version is the release, not the fetch date: it is named after the
directory the time series CSV is published in (".../2025_HDR/..." gives
"hdr2025"), so a new release lands in a new directory. Files are kept as
served under data/raw/<version>/. data/raw/<version>/MANIFEST.json records
for each file its URL, label on the page, size, sha256, Last-Modified,
fetch time, and the CSV's encoding (Windows-1252, not UTF-8). It also keeps
the dated update notes the page states ("06 May 2025 Update: HDR 2025 data
update"). A file whose manifest entry exists and whose sha256 still matches
is not fetched again.

    uv run python scripts/01_download.py
"""

import hashlib
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PAGE_URL = "https://hdr.undp.org/data-center/documentation-and-downloads"
UA = "undp-hdr/1 (+https://github.com/yuiseki/undp-hdr)"
LIMIT_BYTES = 100 * 1000 * 1000
DATA_SUFFIXES = (".csv", ".xlsx", ".xls", ".zip")
TIME_SERIES = re.compile(r"/([0-9]{4}(?:-[0-9]{2})?)_HDR/[^/]*complete_time_series\.csv$")
# The office states the encoding nowhere; the CSV fails as UTF-8 on byte 0xF4
# ("Côte d'Ivoire") and reads cleanly as Windows-1252.
ENCODINGS = {".csv": "windows-1252"}

_last_request = 0.0


class _DataLinks(HTMLParser):
    """Collect <a> links inside <div class="field--name-field-links"> blocks."""

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.depth = 0  # div depth inside a links block, 0 = outside
        self.href: str | None = None
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "field--name-field-links" in (a.get("class") or "").split():
                self.depth = 1
        elif tag == "a" and self.depth and a.get("href"):
            self.href = urllib.parse.urljoin(self.base, a["href"])
            self.text = []

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1
        elif tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join("".join(self.text).split())))
            self.href = None

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)


def parse_data_links(html: str, base: str) -> list[tuple[str, str]]:
    """(url, label) of every data file in the page's "Data links" blocks."""
    p = _DataLinks(base)
    p.feed(html)
    out, seen = [], set()
    for url, label in p.links:
        path = urllib.parse.urlparse(url).path.lower()
        if path.endswith(DATA_SUFFIXES) and url not in seen:
            seen.add(url)
            out.append((url, label))
    return out


def release_version(links: list[tuple[str, str]]) -> str:
    """Name the release after the directory of the time series CSV."""
    for url, _ in links:
        mt = TIME_SERIES.search(urllib.parse.urlparse(url).path)
        if mt:
            return "hdr" + mt.group(1)
    raise SystemExit("no composite indices time series CSV among the data links")


def parse_update_notes(html: str) -> list[str]:
    """Dated notes such as '06 May 2025 Update: HDR 2025 data update'."""
    notes = re.findall(r"(\d{1,2} [A-Z][a-z]+ \d{4} Update:[^<]*)<", html)
    return [" ".join(n.split()) for n in notes]


def encoding_for(name: str) -> str | None:
    return ENCODINGS.get(Path(name).suffix.lower())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _open(url: str, method: str = "GET"):
    global _last_request
    wait = 1.0 - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
    r = urllib.request.urlopen(req, timeout=300)
    _last_request = time.monotonic()
    return r


def get_text(url: str) -> str:
    with _open(url) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8")


def head_length(url: str) -> int | None:
    with _open(url, "HEAD") as r:
        v = r.headers.get("Content-Length")
    return int(v) if v else None


def fetch(url: str, dest: Path) -> dict:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with _open(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
        length = r.headers.get("Content-Length")
        lm = r.headers.get("Last-Modified", "")
    got = tmp.stat().st_size
    if length is not None and got != int(length):
        tmp.unlink()
        raise SystemExit(f"{url}: got {got} bytes, the server stated {length}")
    tmp.replace(dest)
    return {
        "url": url,
        "bytes": got,
        "sha256": sha256(dest),
        "last_modified": lm,
        "fetched_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    html = get_text(PAGE_URL)
    links = parse_data_links(html, PAGE_URL)
    version = release_version(links)
    d = RAW / version
    d.mkdir(parents=True, exist_ok=True)
    mpath = d / "MANIFEST.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {"files": {}}
    files = manifest["files"]

    todo = []
    for url, label in links:
        name = Path(urllib.parse.urlparse(url).path).name
        e = files.get(name)
        if e and e["url"] == url and (d / name).exists() and sha256(d / name) == e["sha256"]:
            continue
        todo.append((url, label, name))

    if todo:
        stated = [head_length(u) for u, _, _ in todo]
        total = sum(n or 0 for n in stated)
        if total > LIMIT_BYTES:
            raise SystemExit(f"{total:,} bytes to fetch exceeds the {LIMIT_BYTES:,} byte limit")

    for url, label, name in todo:
        entry = fetch(url, d / name)
        entry["label"] = label
        enc = encoding_for(name)
        if enc:
            entry["encoding"] = enc
        files[name] = entry
        print(f"{version}/{name}: {entry['bytes']:,} bytes, {entry['last_modified']}")

    manifest.update(
        {
            "release": version,
            "source_page": PAGE_URL,
            "update_notes": parse_update_notes(html),
            "licence": "CC BY 3.0 IGO (https://hdr.undp.org/terms-use)",
        }
    )
    manifest["files"] = dict(sorted(files.items()))
    if todo or not mpath.exists():
        mpath.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"{version}: {len(links)} files listed, {len(todo)} fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
