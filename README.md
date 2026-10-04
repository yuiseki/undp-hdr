# undp-hdr

A reproducible copy of the data files of the current Human Development Report
release from the UNDP Human Development Report Office (HDRO): the Human
Development Index (HDI) and the other composite indices (IHDI, GDI, GII,
PHDI) with their components, and the global Multidimensional Poverty Index
(MPI) tables, which HDRO produces jointly with OPHI (University of Oxford).

- Source page: <https://hdr.undp.org/data-center/documentation-and-downloads>
- Producer: Human Development Report Office, United Nations Development Programme

## What is fetched

Every file in the "Data links" blocks of the source page:

- `HDR25_Composite_indices_complete_time_series.csv`: all composite indices
  and their components, one row per country or aggregate, one column per
  indicator and year (wide format). The file is **Windows-1252**, not UTF-8;
  read it with `encoding="cp1252"`. The manifest records this.
- `HDR25_Composite_indices_metadata.xlsx`: the codebook for that CSV.
- `HDR25_Statistical_Annex_*.xlsx`: the statistical annex tables of the
  report, one per index and one with all tables, in the report's layout.
- `2025_gMPI_Table1and2.xlsx`: MPI tables 1 and 2 (national and subnational).

Not fetched: the report and technical-note PDFs, the "Calculating the
Indices" teaching workbook, past releases, and the hdrdata.org API (it needs
an API key).

The version directory is named after the release directory of the time
series CSV on the server (`.../2025_HDR/...` becomes `hdr2025`), so a new
report goes into a new directory. The MPI tables are updated separately from
the report (the page dates the HDR 2025 data to 6 May 2025 and the MPI 2025
data to 17 October 2025); they are filed with the release current when they
are fetched.

## Licence

All materials on hdr.undp.org are licensed under the Creative Commons
Attribution 3.0 IGO licence (<https://hdr.undp.org/terms-use>, legal code
<http://creativecommons.org/licenses/by/3.0/igo/legalcode>).

The office asks that the HDI data be accompanied by this note: "The entire
series of Human Development Index (HDI) values and rankings are recalculated
every year using the same the most recent (revised) data and functional forms.
The HDI rankings and values in the 2014 Human Development Report cannot
therefore be compared directly to indices published in previous Reports.
Please see hdr.undp.org for more information." (quoted as published, with
the report year of the original wording). In short: HDI values and ranks are
not comparable across reports; compare years only within one release's time
series.

## How to run

```sh
uv run python scripts/01_download.py   # fetch into data/raw/<release>/
uv run python scripts/02_verify.py     # re-hash, test xlsx/zip, count CSV rows
uv run python -m pytest                # unit tests for the page parsing
```

`01_download.py` uses the Python standard library only, waits at least one
second between requests, and skips files whose manifest entry still matches
their sha256.

## Layout

```
scripts/01_download.py   read the source page, fetch the data files, write MANIFEST.json
scripts/02_verify.py     check files against MANIFEST.json
tests/                   unit tests; tests/fixtures/ holds a trimmed copy of the source page
data/raw/<release>/      files as served, plus MANIFEST.json (not in git)
```

`MANIFEST.json` records, for each file, its URL, label on the page, bytes,
sha256, Last-Modified, fetch time (UTC) and, for the CSV, its encoding; and
for the release, the source page, the dated update notes the page states, and
the licence.
