import importlib.util
import zipfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "verify", Path(__file__).parents[1] / "scripts" / "02_verify.py"
)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def test_csv_rows_are_counted_in_the_stated_encoding(tmp_path):
    p = tmp_path / "t.csv"
    p.write_bytes("iso3,country\r\nCIV,C\xf4te d'Ivoire\r\nTUR,T\xfcrkiye\r\n".encode("cp1252"))
    assert m.count_csv_rows(p, "windows-1252") == 2


def test_csv_in_the_wrong_encoding_fails(tmp_path):
    p = tmp_path / "t.csv"
    p.write_bytes("iso3,country\r\nCIV,C\xf4te d'Ivoire\r\n".encode("cp1252"))
    with pytest.raises(UnicodeDecodeError):
        m.count_csv_rows(p, "utf-8")


def test_xlsx_is_tested_as_a_zip(tmp_path):
    p = tmp_path / "t.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    assert m.check_zip(p) is None
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(zipfile.BadZipFile):
        m.check_zip(bad)


@pytest.mark.parametrize(
    ("name", "raw", "want"),
    [
        ("iso3", "JPN", "JPN"),
        ("region", "", None),
        ("hdi_1990", "0.853", 0.853),
        ("hdi_1990", "1", 1.0),
        ("hdi_1990", "", None),
        ("hdi_rank_2023", "23", 23),
        ("rankdiff_hdi_phdi_2023", "-12", -12),
    ],
)
def test_a_csv_cell_is_read_as_the_parquet_should_hold_it(name, raw, want):
    got = m.typed(name, raw)
    assert got == want and type(got) is type(want)


def test_long_rows_skip_labels_and_empty_cells():
    header = ["iso3", "country", "hdicode", "region", "hdi_rank_2023", "hdi_1990"]
    rows = [["JPN", "Japan", "Very High", "", "23", "0.853"], ["PRK", "Korea", "", "EAP", "", ""]]
    assert m.long_rows(header, rows) == {
        ("JPN", "hdi_rank", 2023): 23.0,
        ("JPN", "hdi", 1990): 0.853,
    }
