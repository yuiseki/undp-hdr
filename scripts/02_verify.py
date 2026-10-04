#!/usr/bin/env python3
"""Check every release under data/raw/ against its MANIFEST.json.

Re-hashes each file, tests each zip container (xlsx files are zips) with
zipfile.testzip, reads each gzip to the end, and counts the rows of each CSV
with the csv module in the encoding the manifest records. Prints one ok/FAIL
line per check and exits non-zero on any failure.

    uv run python scripts/02_verify.py
"""

import csv
import gzip
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def count_csv_rows(path: Path, encoding: str) -> int:
    """Data rows (header excluded), decoded strictly in the given encoding."""
    with open(path, newline="", encoding=encoding, errors="strict") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def check_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
    if bad is not None:
        raise zipfile.BadZipFile(f"bad member {bad}")


def check_gzip(path: Path) -> None:
    with gzip.open(path, "rb") as f:
        while f.read(1 << 20):
            pass


def verify(d: Path) -> int:
    failures = 0
    files = json.loads((d / "MANIFEST.json").read_text())["files"]
    for name, e in files.items():
        p = d / name
        tag = f"{d.name}/{name}"
        if not p.exists():
            print(f"FAIL {tag}: missing")
            failures += 1
            continue
        if p.stat().st_size != e["bytes"] or sha256(p) != e["sha256"]:
            print(f"FAIL {tag}: size or sha256 differs from the manifest")
            failures += 1
            continue
        print(f"ok   {tag}: sha256")
        suffix = p.suffix.lower()
        try:
            if suffix in (".zip", ".xlsx"):
                check_zip(p)
                print(f"ok   {tag}: zip")
            elif suffix == ".gz":
                check_gzip(p)
                print(f"ok   {tag}: gzip")
            elif suffix == ".csv":
                n = count_csv_rows(p, e.get("encoding", "utf-8"))
                print(f"ok   {tag}: {n:,} rows ({e.get('encoding', 'utf-8')})")
        except (zipfile.BadZipFile, OSError, EOFError, UnicodeDecodeError, csv.Error) as ex:
            print(f"FAIL {tag}: {ex}")
            failures += 1
    return failures


def main() -> int:
    dirs = sorted(p.parent for p in RAW.glob("*/MANIFEST.json"))
    if not dirs:
        print("FAIL no MANIFEST.json under data/raw/")
        return 1
    failures = sum(verify(d) for d in dirs)
    print("all ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
