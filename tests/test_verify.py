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
