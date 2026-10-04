#!/usr/bin/env python3
"""Push the card, the licence, the provenance, the Parquet and the raw files to the Hub.

Every raw file goes up unchanged after its sha256 is checked against
data/raw/<release>/MANIFEST.json, and the card must declare every Parquet
file under data/parquet/ as a subset named '<release>.<table>'. A new
release is added beside the others.

    uv run python src/publish.py             # dry run: list the files and their total size
    uv run python src/publish.py --push
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "yuiseki/undp-hdr"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def subset_entry(release: str, table: str) -> str:
    return f"- config_name: '{release}.{table}'\n  data_files: parquet/{release}/{table}.parquet\n"


def collect(data: Path) -> list[str]:
    """The files to upload, relative to data/; stops on anything the card or a manifest refutes."""
    card = (data / "README.md").read_text(encoding="utf-8")
    files = ["README.md", "LICENSE", "provenance.yaml"]
    parquet = sorted((data / "parquet").glob("*/*.parquet"))
    if not parquet:
        raise SystemExit("no Parquet under data/parquet/; run scripts/03_export_parquet.py")
    for p in parquet:
        if subset_entry(p.parent.name, p.stem) not in card:
            raise SystemExit(f"the card does not declare the subset {p.parent.name}.{p.stem}")
        files.append(p.relative_to(data).as_posix())
    for mpath in sorted((data / "raw").glob("*/MANIFEST.json")):
        d = mpath.parent
        for name, m in json.loads(mpath.read_text())["files"].items():
            if sha256(d / name) != m["sha256"]:
                raise SystemExit(f"raw/{d.name}/{name} is not the file in its manifest")
            files.append(f"raw/{d.name}/{name}")
        files.append(f"raw/{d.name}/MANIFEST.json")
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    files = collect(DATA)
    total = 0
    for f in files:
        size = (DATA / f).stat().st_size
        total += size
        print(f"  {size:>12,}  {f}")
    print(f"{a.repo}\n  {len(files)} files, {total:,} bytes ({total / 1e6:.1f} MB)")
    if not a.push:
        print("\ndry run. pass --push to upload")
        return 0

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        folder_path=str(DATA), repo_id=a.repo, repo_type="dataset", allow_patterns=files
    )
    print(f"\npushed to https://huggingface.co/datasets/{a.repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
