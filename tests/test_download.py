import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).parent
_spec = importlib.util.spec_from_file_location(
    "download", HERE.parent / "scripts" / "01_download.py"
)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

PAGE = (HERE / "fixtures" / "documentation-and-downloads.html").read_text(encoding="utf-8")
BASE = "https://hdr.undp.org/sites/default/files/"


def test_data_links_are_the_tables_the_csv_and_the_metadata():
    links = m.parse_data_links(PAGE, m.PAGE_URL)
    urls = [u for u, _ in links]
    assert len(urls) == 10
    assert BASE + "2025_HDR/HDR25_Composite_indices_complete_time_series.csv" in urls
    assert BASE + "2025_HDR/HDR25_Composite_indices_metadata.xlsx" in urls
    assert BASE + "2025_HDR/HDR25_Statistical_Annex_Tables_1-7.xlsx" in urls
    assert BASE + "publications/additional-files/2025-10/2025_gMPI_Table1and2.xlsx" in urls
    assert len(set(urls)) == len(urls)


def test_data_links_leave_out_the_tool_the_api_manual_and_pdfs():
    urls = [u for u, _ in m.parse_data_links(PAGE, m.PAGE_URL)]
    assert not any(u.endswith(".pdf") for u in urls)
    assert not any("calculating_indices" in u for u in urls)


def test_data_links_keep_their_labels():
    labels = dict(m.parse_data_links(PAGE, m.PAGE_URL))
    assert (
        labels[BASE + "2025_HDR/HDR25_Composite_indices_complete_time_series.csv"]
        == "All composite indices and components time series (1990-2023)"
    )
    assert labels[BASE + "2025_HDR/HDR25_Composite_indices_metadata.xlsx"] == "Metadata"


def test_data_links_resolve_relative_hrefs():
    html = (
        '<div class="field field--name-field-links"><div class="field__items">'
        '<div class="field__item"><a href="/sites/default/files/2025_HDR/x.csv">X</a></div>'
        "</div></div>"
    )
    assert m.parse_data_links(html, m.PAGE_URL) == [(BASE + "2025_HDR/x.csv", "X")]


def test_release_version_comes_from_the_time_series_directory():
    links = m.parse_data_links(PAGE, m.PAGE_URL)
    assert m.release_version(links) == "hdr2025"


@pytest.mark.parametrize(
    ("directory", "version"),
    [("2025_HDR", "hdr2025"), ("2023-24_HDR", "hdr2023-24"), ("2021-22_HDR", "hdr2021-22")],
)
def test_release_version_naming(directory, version):
    url = f"{BASE}{directory}/HDRxx_Composite_indices_complete_time_series.csv"
    assert m.release_version([(url, "t")]) == version


def test_release_version_refuses_a_page_without_the_time_series():
    with pytest.raises(SystemExit):
        m.release_version([(BASE + "2025_HDR/HDR25_Statistical_Annex_HDI_Table.xlsx", "t")])


def test_update_notes():
    assert m.parse_update_notes(PAGE) == [
        "17 October 2025 Update: MPI 2025 data update",
        "06 May 2025 Update: HDR 2025 data update",
        "16 April 2024 Update: HDRO released Data API 2.0",
    ]


def test_csv_encoding_is_windows_1252():
    assert m.encoding_for("HDR25_Composite_indices_complete_time_series.csv") == "windows-1252"
    assert m.encoding_for("HDR25_Composite_indices_metadata.xlsx") is None
