---
license: other
license_name: cc-by-3.0-igo
license_link: https://creativecommons.org/licenses/by/3.0/igo/legalcode
language:
- en
task_categories:
- tabular-regression
- time-series-forecasting
tags:
- human-development
- hdi
- undp
- development-indicators
- gender
- inequality
- poverty
size_categories:
- 100K<n<1M
configs:
- config_name: 'hdr2025.composite_indices_long'
  data_files: parquet/hdr2025/composite_indices_long.parquet
  default: true
- config_name: 'hdr2025.composite_indices'
  data_files: parquet/hdr2025/composite_indices.parquet
---

# undp-hdr

The statistics of the Human Development Report of the United Nations
Development Programme (UNDP), as its Human Development Report Office (HDRO)
publishes them at https://hdr.undp.org/data-center/documentation-and-downloads:
the Human Development Index (HDI) and the other composite indices (the
Gender Development Index GDI, the Inequality-adjusted HDI IHDI, the Gender
Inequality Index GII and the Planetary pressures-adjusted HDI PHDI) with
their components, for 195 countries and territories and 11 aggregates, 1990
to 2023. Beside them are the statistical annex tables of the report and the
global Multidimensional Poverty Index (MPI) tables, which HDRO produces
jointly with OPHI (University of Oxford), unchanged.

Licensed under Creative Commons Attribution 3.0 IGO (see Licence).

HDRO recalculates the whole series every year. In its words: "The entire
series of Human Development Index (HDI) values and rankings are recalculated
every year using the same the most recent (revised) data and functional
forms. The HDI rankings and values in the 2014 Human Development Report
cannot therefore be compared directly to indices published in previous
Reports. Please see hdr.undp.org for more information." (quoted as
published, with the report year of the original wording). Values and ranks
from different reports are not comparable; compare years within one
release's time series only.

## Releases

One subset per table and release. A release is named after the directory
of the report on hdr.undp.org (`.../2025_HDR/...` is `hdr2025`); a new
report will be added beside it, not over it.

| subset | rows | made from |
|---|---:|---|
| `hdr2025.composite_indices_long` | 200,004 | `raw/hdr2025/HDR25_Composite_indices_complete_time_series.csv` |
| `hdr2025.composite_indices` | 206 | the same CSV |

`hdr2025` is the Human Development Report 2025, whose data HDRO updated on
6 May 2025. It was the current release when the files were fetched on
2026-10-04; HDR 2026 data had not been published. The MPI tables in
`raw/hdr2025/` are the MPI 2025 update of 17 October 2025, filed with the
release that was current when they were fetched.

All the raw files are HDRO's own, byte for byte, in `raw/hdr2025/`; its
`MANIFEST.json` gives their URLs, sizes, sha256 and Last-Modified.

| file | what it is | here as |
|---|---|---|
| `HDR25_Composite_indices_complete_time_series.csv` | every composite index and component, 1990 to 2023 | raw, and the two Parquet subsets |
| `HDR25_Composite_indices_metadata.xlsx` | the codebook of that CSV, and the recommended citation | raw only |
| `HDR25_Statistical_Annex_HDI_Table.xlsx` | annex table 1, HDI | raw only |
| `HDR25_Statistical_Annex_HDI_Trends_Table.xlsx` | annex table 2, HDI trends | raw only |
| `HDR25_Statistical_Annex_IHDI_Table.xlsx` | annex table 3, IHDI | raw only |
| `HDR25_Statistical_Annex_GDI_Table.xlsx` | annex table 4, GDI | raw only |
| `HDR25_Statistical_Annex_GII_Table.xlsx` | annex table 5, GII | raw only |
| `HDR25_Statistical_Annex_PHDI_Table.xlsx` | annex table 7, PHDI | raw only |
| `HDR25_Statistical_Annex_Tables_1-7.xlsx` | the six annex tables in one workbook | raw only |
| `2025_gMPI_Table1and2.xlsx` | MPI tables 1 (national) and 2 (subnational) | raw only |

The xlsx files are not converted. They are tables laid out for the printed
report: a title row, two to four rows of headings and units, rows that name
a group of countries in the middle of the data, a column of footnote letters
beside many value columns, and notes below the table. The codebook sheet of
the metadata workbook has a heading row between its sections. None of them
is a table of one header row and one record per row. Most values of the
annex tables are also in the time series CSV; some are not, for example the
income shares and the inequality-adjusted component indices of table 3 and
the GNI per capita rank minus HDI rank of table 1. The MPI is not in the
CSV at all.

## Files and columns

### composite_indices (wide)

The CSV as it is: one row per country or aggregate, 1,112 columns in the
order of the CSV. The first four label the row; each of the other 1,108 is
one indicator in one year, named `<indicator>_<year>`, for example
`hdi_1990` or `gni_pc_f_2023`. The type comes from the column name, never
from inference:

| columns | type |
|---|---|
| `iso3`, `country`, `hdicode`, `region` | VARCHAR |
| `hdi_rank_2023`, `gii_rank_2023`, `gdi_group_2023`, `rankdiff_hdi_phdi_2023` | INTEGER |
| every other `<indicator>_<year>`, for the 36 indicators of the codebook below | DOUBLE |
| a column that fits none of these (there is none in hdr2025) | VARCHAR |

An empty cell is NULL. Each value was checked against a regular expression
(`-?[0-9]+` for INTEGER, `-?[0-9]+(\.[0-9]+)?` for DOUBLE) before the cast,
and a value that did not fit would have stopped the build.

### composite_indices_long

The same values, one row per filled cell of the 1,108 value columns:
1,108 x 206 = 228,248 cells, of which 28,244 are empty and left out.

| column | type | from |
|---|---|---|
| `iso3` | VARCHAR | the row's `iso3` |
| `country` | VARCHAR | the row's `country` |
| `region` | VARCHAR | the row's `region` (NULL where the CSV is empty) |
| `indicator` | VARCHAR | the column name before its last underscore |
| `year` | INTEGER | the four digits after it |
| `value` | DOUBLE | the cell |

The rule: a column name `<indicator>_<year>` is split at its last
underscore when four digits follow it, so `hdi_1990` is `hdi` and 1990,
`gni_pc_f_2023` is `gni_pc_f` and 2023, and `hdi_rank_2023` is `hdi_rank`
and 2023. `value` is DOUBLE for every indicator; the ranks and groups are
small integers and a DOUBLE holds them exactly. `hdicode` is not repeated
here; join the wide table on `iso3` for it. Rows are sorted by `indicator`,
`iso3` and `year`.

### Indicators

From the codebook sheet of `HDR25_Composite_indices_metadata.xlsx` (the
names as written there):

| index | indicator | full name | years |
|---|---|---|---|
| HDI | `hdi_rank` | HDI Rank | 2023 |
| HDI | `hdi` | Human Development Index (value) | 1990-2023 |
| HDI | `le` | Life Expectancy at Birth (years) | 1990-2023 |
| HDI | `eys` | Expected Years of Schooling (years) | 1990-2023 |
| HDI | `mys` | Mean Years of Schooling (years) | 1990-2023 |
| HDI | `gnipc` | Gross National Income Per Capita (2021 PPP$) | 1990-2023 |
| GDI | `gdi_group` | GDI Group | 2023 |
| GDI | `gdi` | Gender Development Index (value) | 1990-2023 |
| GDI | `hdi_f`, `hdi_m` | HDI female, male (value) | 1990-2023 |
| GDI | `le_f`, `le_m` | Life Expectancy at Birth, female, male (years) | 1990-2023 |
| GDI | `eys_f`, `eys_m` | Expected Years of Schooling, female, male (years) | 1990-2023 |
| GDI | `mys_f`, `mys_m` | Mean Years of Schooling, female, male (years) | 1990-2023 |
| GDI | `gni_pc_f`, `gni_pc_m` | Gross National Income Per Capita, female, male (2021 PPP$) | 1990-2023 |
| IHDI | `ihdi` | Inequality-adjusted Human Development Index (value) | 2010-2023 |
| IHDI | `coef_ineq` | Coefficient of human inequality | 2010-2023 |
| IHDI | `loss` | Overall loss (%) | 2010-2023 |
| IHDI | `ineq_le` | Inequality in life expectancy | 2010-2023 |
| IHDI | `ineq_edu` | Inequality in eduation (sic) | 2010-2023 |
| IHDI | `ineq_inc` | Inequality in income | 2010-2021, 2022-2023=2022 |
| GII | `gii_rank` | GII Rank | 2023 |
| GII | `gii` | Gender Inequality Index (value) | 1990-2023 |
| GII | `mmr` | Maternal Mortality Ratio (deaths per 100,000 live births) | 1990-2019, 2020-2023=2020 |
| GII | `abr` | Adolescent Birth Rate (births per 1,000 women ages 15-19) | 1990-2023 |
| GII | `se_f`, `se_m` | Population with at least some secondary education, female, male (% ages 25 and older) | 1990-2023 |
| GII | `pr_f`, `pr_m` | Share of seats in parliament, female (% held by women), male (% held by men) | 1990-2023 |
| GII | `lfpr_f`, `lfpr_m` | Labour force participation rate, female, male (% ages 15 and older) | 1990-2023 |
| PHDI | `rankdiff_hdi_phdi` | Difference from HDI rank | 2023 |
| PHDI | `phdi` | Planetary pressures-adjusted Human Development Index (value) | 1990-2023 |
| PHDI | `diff_hdi_phdi` | Difference from HDI value (%) | 1990-2023 |
| PHDI | `co2_prod` | Carbon dioxide emissions per capita (production) (tonnes) | 1990-2023 |
| PHDI | `mf` | Material footprint per capita (tonnes) | 1990-2023 |
| additional | `pop_total` | Population, total (millions) | 1990-2023 |

The codebook has years 1990-2023 for every indicator not listed with
another range, and the CSV has a column for each of those years even where
the index itself starts later: the IHDI columns run from 2010 only.

```sql
-- DuckDB, straight off the Hub: HDI of Japan, Norway and Niger over time, HDR 2025
SELECT iso3, country, year, value AS hdi
FROM 'hf://datasets/yuiseki/undp-hdr/parquet/hdr2025/composite_indices_long.parquet'
WHERE indicator = 'hdi' AND iso3 IN ('JPN', 'NOR', 'NER')
ORDER BY iso3, year;

-- the wide table, countries only, ranked by HDI 2023
SELECT iso3, country, hdicode, hdi_rank_2023, hdi_2023, le_2023, gnipc_2023
FROM 'hf://datasets/yuiseki/undp-hdr/parquet/hdr2025/composite_indices.parquet'
WHERE iso3 NOT LIKE 'ZZ%'
ORDER BY hdi_rank_2023;
```

## Things to know

- The rows are not all countries. 195 have a three-letter country code in
  `iso3`; 11 are aggregates whose `iso3` begins with `ZZ`: the four HDI
  groups (`ZZA.VHHD`, `ZZB.HHD`, `ZZC.MHD`, `ZZD.LHD`), the six developing
  regions (`ZZE.AS` to `ZZJ.SSA`) and the world (`ZZK.WORLD`). Leave out
  `iso3 LIKE 'ZZ%'` to keep countries only; the aggregates have no
  `hdicode` and no `region`.
- `hdicode` is Very High (74), High (50), Medium (43), Low (26) or "Other
  Countries or Territories" (2: the Democratic People's Republic of Korea
  and Monaco, which have no HDI). `region` is the UNDP developing region
  (SSA 46, LAC 33, EAP 26, AS 20, ECA 17, SA 9); it is empty for the 44
  countries outside them, as well as for the aggregates.
- Some values are not observations. The codebook gives `mmr` as "1990-2019,
  2020-2023=2020" and `ineq_inc` as "2010-2021, 2022-2023=2022": for every
  country, `mmr` of 2021, 2022 and 2023 equals `mmr` of 2020, and
  `ineq_inc` of 2023 equals that of 2022. Only the 11 aggregates differ
  between those years.
- Ranks share places: `hdi_rank_2023` has ties (Norway and Switzerland are
  both 2), and 193 rows have one.
- `pr_f` and `pr_m` add to 100 wherever both are filled.
- Of the 228,248 value cells, 28,244 are empty. In 2023, `hdi` is filled
  for 193 countries, `gdi` for 184, `gii` for 172, `ihdi` for 169 and `phdi`
  for 156; in 1990, `hdi` for 141 countries.
- The CSV is Windows-1252, not UTF-8. Only two rows are outside ASCII
  (Côte d'Ivoire and Türkiye); the Parquet holds them as UTF-8.
- The annex xlsx hold the same 2023 values as the CSV without the CSV's
  rounding (0.97199999999999998 in the xlsx against 0.972 in the CSV for
  Iceland's HDI).
- Many components come from other agencies (UNDESA, UNESCO, the World
  Bank, the IMF, the ILO, the IPU, WHO and others, listed in the Technical
  Notes of the report); the indices are HDRO's calculations from them.

## Checked before upload

`scripts/02_verify.py` in the source repository checks, with Python's csv
module reading the CSV in Windows-1252 and DuckDB reading the Parquet:

- every raw file has the size and sha256 in `MANIFEST.json`, and every xlsx
  is a sound zip
- the CSV has 206 rows; `composite_indices` has 206 rows and the CSV's
  1,112 column names in the same order, each of the type the rule gives
- all 229,072 cells of `composite_indices` equal the CSV's, compared one by
  one: text as text, numbers as Python's int and float read them, an empty
  cell as NULL
- `composite_indices_long` has 200,004 rows, one per filled value cell, and
  the same value for every (iso3, indicator, year), with the row's
  `country` and `region`
- a DuckDB with extension autoloading turned off opens both files
- no row group of either file has a bloom filter

## Licence

hdr.undp.org, Terms of use (https://hdr.undp.org/terms-use, read on
2026-10-04):

> Creative Commons Attribution 3.0 IGO
> All materials provided on this website are copyrighted under the Creative
> Commons Attribution 3.0 IGO license. This International Governmental
> Organizations license was developed under the auspices of the World
> Intellectual Property Organization (WIPO) and has been adopted by a number
> of other international organizations, such as CERN, ILO, OECD, WHO, UNESCO
> and the UN.

> You are free to:
> Share - copy and redistribute the material in any medium or format
> Adapt - remix, transform, and build upon the material for any purpose,
> even commercially.

> Appropriate Credit
> You must give appropriate credit, provide a link to the license, and
> indicate where changes were made. You may do so in any reasonable manner,
> but in no way that suggests the licensor endorses you or your use.

(The separators in the original are dashes; they are written `-` here.)

The same page asks that the materials be used in line with the principles
of the United Nations Charter, and, under "Latest available Data", that
data incorporated in internal servers be the latest available and follow
its updates. This dataset names its release (`hdr2025`) on every subset so
that a newer release is not mistaken for this one.

The legal code is at https://creativecommons.org/licenses/by/3.0/igo/legalcode.
The card declares `license: other` with `license_name: cc-by-3.0-igo`,
which names this licence exactly; CC BY 3.0 IGO is not CC BY 3.0 (unported)
and differs from it in, among other things, its dispute resolution by
mediation and arbitration and its preservation of the privileges and
immunities of the licensor.

This dataset is not made or endorsed by UNDP or HDRO. What was changed: the
time series CSV was decoded from Windows-1252, typed and written as Parquet
in two shapes (wide and long), as described above; no value was changed.
The raw files are unchanged. `LICENSE` beside this file says the same.

The report itself (the PDF) carries "All rights reserved" in its imprint;
it is not here. The time series and the metadata carry no licence text of
their own, so the site's terms apply to them.

## Citation

The citation HDRO recommends, from the `recommended_citation` sheet of
`HDR25_Composite_indices_metadata.xlsx` (the separator in the original is a
dash):

> Source: UNDP (United Nations Development Programme). 2025. Human
> Development Report 2025 - A matter of choice: People and possibilities in
> the age of AI. New York.

The global MPI tables are produced jointly by HDRO and OPHI (Oxford
Poverty and Human Development Initiative, University of Oxford).
