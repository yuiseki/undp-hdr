import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "publish", Path(__file__).parents[1] / "src" / "publish.py"
)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def _data(tmp_path, card_tables=("t",), raw=b"x", manifest_raw=b"x"):
    d = tmp_path / "data"
    (d / "parquet" / "r1").mkdir(parents=True)
    (d / "parquet" / "r1" / "t.parquet").write_bytes(b"PAR1")
    (d / "raw" / "r1").mkdir(parents=True)
    (d / "raw" / "r1" / "f.csv").write_bytes(raw)
    files = {"f.csv": {"sha256": hashlib.sha256(manifest_raw).hexdigest()}}
    (d / "raw" / "r1" / "MANIFEST.json").write_text(json.dumps({"files": files}))
    card = "---\nconfigs:\n" + "".join(m.subset_entry("r1", t) for t in card_tables) + "---\n"
    (d / "README.md").write_text(card)
    for f in ("LICENSE", "provenance.yaml"):
        (d / f).write_text("x")
    return d


def test_collect_lists_card_parquet_and_raw(tmp_path):
    assert m.collect(_data(tmp_path)) == [
        "README.md", "LICENSE", "provenance.yaml", "parquet/r1/t.parquet",
        "raw/r1/f.csv", "raw/r1/MANIFEST.json",
    ]  # fmt: skip


def test_a_parquet_the_card_does_not_declare_stops_it(tmp_path):
    with pytest.raises(SystemExit, match="r1.t"):
        m.collect(_data(tmp_path, card_tables=("other",)))


def test_a_raw_file_unlike_its_manifest_stops_it(tmp_path):
    with pytest.raises(SystemExit, match="raw/r1/f.csv"):
        m.collect(_data(tmp_path, raw=b"changed"))
