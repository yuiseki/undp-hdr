#!/usr/bin/env python3
"""Check every release under data/raw/ against its MANIFEST.json.

Re-hashes each file, tests each zip container (xlsx files are zips) with
zipfile.testzip, reads each gzip to the end, and counts the rows of each CSV
with the csv module in the encoding the manifest records.

Then checks the Parquet that scripts/03_export_parquet.py made from the
composite indices time series CSV, against the CSV read with the csv module:
  - composite_indices.parquet has as many rows as the CSV, its columns in the
    same order, every column of the type column_type gives its name, and
    every cell equal to the CSV's (text as text, numbers as Python reads
    them, an empty cell as NULL), compared one by one
  - composite_indices_long.parquet has one row per filled value cell, and
    the same (iso3, indicator, year) to value mapping, country and region
  - a plain DuckDB with extension autoloading turned off opens both files
  - no row group carries a bloom filter

Prints one ok/FAIL line per check and exits non-zero on any failure.

    uv run python scripts/02_verify.py
"""

import csv
import gzip
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PQ = ROOT / "data" / "parquet"

_spec = importlib.util.spec_from_file_location("export", ROOT / "scripts" / "03_export_parquet.py")
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)


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


def read_csv(path: Path, encoding: str) -> tuple[list[str], list[list[str]]]:
    with open(path, newline="", encoding=encoding, errors="strict") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def typed(name: str, raw: str):
    """What the Parquet should hold for one CSV cell."""
    if raw == "":
        return None
    t = export.column_type(name)
    if t == "INTEGER":
        return int(raw)
    if t == "DOUBLE":
        return float(raw)
    return raw


def long_rows(header: list[str], rows: list[list[str]]) -> dict:
    """(iso3, indicator, year) -> value for every filled value cell."""
    out = {}
    for row in rows:
        for name, raw in zip(header, row, strict=True):
            if name in export.LABELS or raw == "":
                continue
            indicator, year = export.split_column(name)
            out[(row[0], indicator, year)] = float(raw)
    return out


def verify_parquet(d: Path, files: dict) -> int:
    import duckdb

    failures = 0

    def check(ok: bool, what: str) -> None:
        nonlocal failures
        print(("ok   " if ok else "FAIL ") + f"{d.name}/{what}")
        failures += not ok

    name = next(n for n in files if Path(n).match(export.CSV_GLOB))
    header, rows = read_csv(d / name, files[name].get("encoding", "utf-8"))
    wide = PQ / d.name / "composite_indices.parquet"
    long = PQ / d.name / "composite_indices_long.parquet"
    for p in (wide, long):
        if not p.exists():
            check(False, f"{p.name}: missing")
            return failures

    con = duckdb.connect()
    con.execute("set memory_limit = '8GB'")
    rel = con.sql(f"select * from '{wide}'")
    check(rel.columns == header, f"{wide.name}: {len(rel.columns):,} columns as in the CSV")
    types = dict(zip(rel.columns, (str(t) for t in rel.types), strict=True))
    wrong = {c: t for c, t in types.items() if t != export.column_type(c)}
    check(not wrong, f"{wide.name}: every column has the type its name gives ({wrong or 'all'})")
    got = rel.fetchall()
    check(len(got) == len(rows), f"{wide.name}: {len(got):,} rows, the CSV has {len(rows):,}")
    diff = [
        (r[0], c, raw, g)
        for r, prow in zip(rows, got, strict=False)
        for c, raw, g in zip(header, r, prow, strict=True)
        if typed(c, raw) != g
    ]
    cells = len(rows) * len(header)
    check(not diff, f"{wide.name}: all {cells:,} cells equal the CSV ({diff[:3] or 'none differ'})")

    want = long_rows(header, rows)
    lrows = con.sql(
        f"select iso3, country, region, indicator, year, value from '{long}'"
    ).fetchall()
    check(len(lrows) == len(want), f"{long.name}: {len(lrows):,} rows, {len(want):,} filled cells")
    have = {(r[0], r[3], r[4]): r[5] for r in lrows}
    check(have == want, f"{long.name}: every (iso3, indicator, year, value) as in the CSV")
    labels = {r[0]: (r[1], r[3] or None) for r in rows}
    bad = {r[0] for r in lrows if labels.get(r[0]) != (r[1], r[2])}
    check(not bad, f"{long.name}: country and region as in the CSV ({sorted(bad) or 'all'})")

    plain = duckdb.connect(
        config={"autoload_known_extensions": False, "autoinstall_known_extensions": False}
    )
    for p in (wide, long):
        n = plain.sql(f"select count(*) from '{p}' where iso3 = 'JPN'").fetchone()[0]
        check(n > 0, f"{p.name}: a DuckDB without extensions opens it ({n:,} rows for JPN)")
        bloom = con.sql(
            "select count(*) filter (where bloom_filter_offset is not null) "
            f"from parquet_metadata('{p}')"
        ).fetchone()[0]
        check(bloom == 0, f"{p.name}: no bloom filters")
    return failures


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
    # the Parquet is compared with the CSV, so only once the CSV is the one fetched
    return failures or verify_parquet(d, files)


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
