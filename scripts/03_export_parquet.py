#!/usr/bin/env python3
"""Turn each release's composite indices time series CSV into two Parquet files.

    data/parquet/<release>/composite_indices.parquet       the CSV as it is: 1,112 columns
    data/parquet/<release>/composite_indices_long.parquet  one row per filled cell

The CSV is Windows-1252, so it is first decoded strictly in the encoding its
MANIFEST.json records and written as UTF-8 to data/work/<release>/, which
DuckDB then reads with every column as text.

Types come from the column names, never from inference. The four row labels
(iso3, country, hdicode, region) are text. Every other column is named
<indicator>_<year>; the indicators are those of the codebook in
HDR25_Composite_indices_metadata.xlsx. The four ranks and groups (hdi_rank,
gii_rank, gdi_group, rankdiff_hdi_phdi) are INTEGER, the 36 other indicators
DOUBLE. A column whose name does not fit this rule stays text. Each value is
checked with a regular expression before the cast; a value that does not fit
stops the run with the file, the column and the value. An empty cell is NULL.

The long table is (iso3, country, region, indicator, year, value). indicator
and year are the column name split at its last underscore when what follows
is four digits: hdi_1990 is (hdi, 1990), gni_pc_f_2023 is (gni_pc_f, 2023),
hdi_rank_2023 is (hdi_rank, 2023). value is DOUBLE for every indicator (ranks
and groups are small integers, which a DOUBLE holds exactly). Empty cells are
left out. Rows are sorted by indicator, iso3 and year.

    uv run python scripts/03_export_parquet.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "parquet"
WORK = ROOT / "data" / "work"
CSV_GLOB = "*_Composite_indices_complete_time_series.csv"

LABELS = ("iso3", "country", "hdicode", "region")
# from the codebook sheet of HDR25_Composite_indices_metadata.xlsx
INTEGER_INDICATORS = {"hdi_rank", "gii_rank", "gdi_group", "rankdiff_hdi_phdi"}
DOUBLE_INDICATORS = {
    "hdi", "le", "eys", "mys", "gnipc",
    "gdi", "hdi_f", "le_f", "eys_f", "mys_f", "gni_pc_f", "hdi_m", "le_m", "eys_m", "mys_m", "gni_pc_m",
    "ihdi", "coef_ineq", "loss", "ineq_le", "ineq_edu", "ineq_inc",
    "gii", "mmr", "abr", "se_f", "se_m", "pr_f", "pr_m", "lfpr_f", "lfpr_m",
    "phdi", "diff_hdi_phdi", "co2_prod", "mf",
    "pop_total",
}  # fmt: skip
INTEGER_RE = "-?[0-9]+"
NUMBER_RE = r"-?[0-9]+(\.[0-9]+)?"
COPY = "format parquet, compression zstd, write_bloom_filter false"


def split_column(name: str) -> tuple[str, int] | None:
    m = re.fullmatch(r"(.+)_([0-9]{4})", name)
    return (m.group(1), int(m.group(2))) if m else None


def column_type(name: str) -> str:
    s = split_column(name)
    if s is None:
        return "VARCHAR"
    if s[0] in INTEGER_INDICATORS:
        return "INTEGER"
    if s[0] in DOUBLE_INDICATORS:
        return "DOUBLE"
    return "VARCHAR"


def _expr(label: str, name: str) -> str:
    c, t = f'"{name}"', column_type(name)
    if t == "VARCHAR":
        return c
    pattern, what = (INTEGER_RE, "an integer") if t == "INTEGER" else (NUMBER_RE, "a number")
    return (
        f"case when {c} is null then null "
        f"when regexp_full_match({c}, '{pattern}') then cast({c} as {t}) "
        f"else error('{label}: {name} is not {what}: ' || {c}) end"
    )


def select_sql(con, path: Path, label: str) -> str:
    """The wide table: every column of the CSV, in its order, typed by name."""
    src = f"read_csv('{path}', header = true, all_varchar = true, strict_mode = true)"
    names = con.sql(f"select * from {src} limit 0").columns
    cols = [f'{_expr(label, n)} as "{n}"' for n in names]
    return f"select {', '.join(cols)} from {src}"


def long_sql(wide: str, columns: list[str]) -> str:
    """The long table from the wide one: one row per filled <indicator>_<year> cell."""
    values = [c for c in columns if c not in LABELS]
    text = [c for c in values if column_type(c) == "VARCHAR"]
    if text:
        raise ValueError(f"columns without a numeric type: {text}")
    on = ", ".join(f'"{c}"' for c in values)
    cast = ", ".join(f'cast("{c}" as double) as "{c}"' for c in values)
    return (
        "select iso3, country, region, "
        "regexp_extract(col, '^(.+)_([0-9]{4})$', 1) as indicator, "
        "cast(regexp_extract(col, '^(.+)_([0-9]{4})$', 2) as integer) as year, value "
        f"from (unpivot (select iso3, country, region, {cast} from {wide}) "
        f"on {on} into name col value value) "
        "order by indicator, iso3, year"
    )


def transcode(src: Path, dst: Path, encoding: str) -> None:
    """Decode strictly (a byte the encoding does not define stops the run), write UTF-8."""
    with open(src, newline="", encoding=encoding, errors="strict") as f:
        text = f.read()
    with open(dst, "w", newline="", encoding="utf-8") as f:
        f.write(text)


def main() -> int:
    import duckdb

    con = duckdb.connect()
    con.execute("set memory_limit = '8GB'")
    manifests = sorted(RAW.glob("*/MANIFEST.json"))
    if not manifests:
        raise SystemExit("no data/raw/<release>/MANIFEST.json")
    for mpath in manifests:
        release = mpath.parent.name
        files = json.loads(mpath.read_text())["files"]
        names = [n for n in files if Path(n).match(CSV_GLOB)]
        if len(names) != 1:
            raise SystemExit(f"{release}: expected one {CSV_GLOB}, found {names}")
        name = names[0]
        work = WORK / release
        work.mkdir(parents=True, exist_ok=True)
        utf8 = work / name
        transcode(mpath.parent / name, utf8, files[name].get("encoding", "utf-8"))

        out = OUT / release
        out.mkdir(parents=True, exist_ok=True)
        wide = out / "composite_indices.parquet"
        con.execute(f"copy ({select_sql(con, utf8, name)}) to '{wide}' ({COPY})")
        cols = con.sql(f"select * from '{wide}' limit 0").columns
        long = out / "composite_indices_long.parquet"
        con.execute(f"copy ({long_sql(repr(str(wide)), cols)}) to '{long}' ({COPY})")
        utf8.unlink()

        for p in (wide, long):
            n = con.sql(f"select count(*) from '{p}'").fetchone()[0]
            print(f"{release}: {p.name} {n:,} rows, {p.stat().st_size:,} bytes", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
