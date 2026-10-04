import importlib.util
from pathlib import Path

import duckdb
import pytest

_spec = importlib.util.spec_from_file_location(
    "export", Path(__file__).parents[1] / "scripts" / "03_export_parquet.py"
)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


@pytest.mark.parametrize(
    ("name", "sql"),
    [
        ("iso3", "VARCHAR"),
        ("country", "VARCHAR"),
        ("hdicode", "VARCHAR"),
        ("region", "VARCHAR"),
        ("hdi_1990", "DOUBLE"),
        ("gni_pc_f_2023", "DOUBLE"),
        ("pop_total_2000", "DOUBLE"),
        ("diff_hdi_phdi_2023", "DOUBLE"),
        ("hdi_rank_2023", "INTEGER"),
        ("gii_rank_2023", "INTEGER"),
        ("gdi_group_2023", "INTEGER"),
        ("rankdiff_hdi_phdi_2023", "INTEGER"),
        ("an_indicator_not_in_the_codebook_2023", "VARCHAR"),
        ("hdi", "VARCHAR"),
        ("hdi_90", "VARCHAR"),
    ],
)
def test_column_type(name, sql):
    assert m.column_type(name) == sql


@pytest.mark.parametrize(
    ("name", "want"),
    [
        ("hdi_1990", ("hdi", 1990)),
        ("hdi_rank_2023", ("hdi_rank", 2023)),
        ("gni_pc_f_2010", ("gni_pc_f", 2010)),
        ("rankdiff_hdi_phdi_2023", ("rankdiff_hdi_phdi", 2023)),
        ("iso3", None),
        ("region", None),
        ("hdi_90", None),
    ],
)
def test_indicator_and_year_come_from_the_column_name(name, want):
    assert m.split_column(name) == want


HEADER = "iso3,country,hdicode,region,hdi_rank_2023,hdi_1990,rankdiff_hdi_phdi_2023,note_2023\n"


def _csv(tmp_path, text):
    f = tmp_path / "t.csv"
    f.write_text(text, encoding="utf-8")
    return f


def _rel(tmp_path, text):
    con = duckdb.connect()
    return con.sql(m.select_sql(con, _csv(tmp_path, text), "T.csv"))


def test_values_are_typed_and_text_stays_text(tmp_path):
    rel = _rel(tmp_path, HEADER + "JPN,Japan,Very High,,23,0.853,-12,x\n")
    row = dict(zip(rel.columns, rel.fetchone(), strict=True))
    assert row == {
        "iso3": "JPN", "country": "Japan", "hdicode": "Very High", "region": None,
        "hdi_rank_2023": 23, "hdi_1990": 0.853, "rankdiff_hdi_phdi_2023": -12, "note_2023": "x",
    }  # fmt: skip
    types = dict(zip(rel.columns, (str(t) for t in rel.types), strict=True))
    assert types["hdi_rank_2023"] == "INTEGER" and types["hdi_1990"] == "DOUBLE"


def test_an_empty_cell_is_null(tmp_path):
    rel = _rel(tmp_path, HEADER + "PRK,Korea (Democratic People's Rep. of),,EAP,,,,\n")
    assert rel.select("hdi_rank_2023, hdi_1990").fetchone() == (None, None)


def test_an_integer_written_without_decimals_is_a_double(tmp_path):
    rel = _rel(tmp_path, HEADER + "X,X,,,1,1,1,\n")
    assert rel.select("hdi_1990").fetchone() == (1.0,)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("X,X,,,1.5,0.5,1,\n", "T.csv: hdi_rank_2023 is not an integer: 1.5"),
        ("X,X,,,1,0.5,n/a,\n", "T.csv: rankdiff_hdi_phdi_2023 is not an integer: n/a"),
        ("X,X,,,1,..,1,\n", r"T.csv: hdi_1990 is not a number: \.\."),
        ("X,X,,,1,1e-3,1,\n", "T.csv: hdi_1990 is not a number: 1e-3"),
        ('X,X,,,1,"0,853",1,\n', "T.csv: hdi_1990 is not a number: 0,853"),
        ("X,X,,,1,.5,1,\n", r"T.csv: hdi_1990 is not a number: \.5"),
    ],
)
def test_a_value_that_does_not_fit_stops_the_run(tmp_path, line, message):
    with pytest.raises(duckdb.Error, match=message):
        _rel(tmp_path, HEADER + line).fetchall()


def test_long_table_has_one_row_per_filled_cell(tmp_path):
    con = duckdb.connect()
    src = _csv(
        tmp_path,
        "iso3,country,hdicode,region,hdi_rank_2023,hdi_1990,hdi_2023\n"
        "JPN,Japan,Very High,,23,0.853,0.925\n"
        "AFG,Afghanistan,Low,SA,,,0.496\n",
    )
    con.execute(f"create table w as {m.select_sql(con, src, 'T.csv')}")
    rel = con.sql(m.long_sql("w", con.sql("select * from w").columns))
    assert rel.columns == ["iso3", "country", "region", "indicator", "year", "value"]
    assert [str(t) for t in rel.types] == [
        "VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "INTEGER", "DOUBLE",
    ]  # fmt: skip
    assert sorted(rel.fetchall()) == [
        ("AFG", "Afghanistan", "SA", "hdi", 2023, 0.496),
        ("JPN", "Japan", None, "hdi", 1990, 0.853),
        ("JPN", "Japan", None, "hdi", 2023, 0.925),
        ("JPN", "Japan", None, "hdi_rank", 2023, 23.0),
    ]


def test_long_table_refuses_a_text_value_column(tmp_path):
    with pytest.raises(ValueError, match="note_2023"):
        m.long_sql("w", ["iso3", "country", "hdicode", "region", "hdi_1990", "note_2023"])


def test_windows_1252_is_transcoded_to_utf8(tmp_path):
    src = tmp_path / "in.csv"
    src.write_bytes("iso3,country\r\nCIV,C\xf4te d'Ivoire\r\nTUR,T\xfcrkiye\r\n".encode("cp1252"))
    dst = tmp_path / "out.csv"
    m.transcode(src, dst, "windows-1252")
    want = "iso3,country\r\nCIV,Côte d'Ivoire\r\nTUR,Türkiye\r\n"
    assert dst.read_bytes() == want.encode("utf-8")


def test_a_byte_windows_1252_does_not_define_stops_the_run(tmp_path):
    src = tmp_path / "in.csv"
    src.write_bytes(b"iso3,country\r\nX,\x81\r\n")
    with pytest.raises(UnicodeDecodeError):
        m.transcode(src, tmp_path / "out.csv", "windows-1252")
