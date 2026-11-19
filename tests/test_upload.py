"""Unit tests for backend.upload module."""

import io
import os
import tempfile
import pytest
import pandas as pd

from backend.upload import (
    load_dataset,
    load_csv,
    load_excel,
    validate_file_source,
    get_supported_formats,
    DataFixUploadError,
    InvalidFileFormatError,
    EmptyFileError,
    FileParsingError,
)


class DummyStreamlitFile(io.BytesIO):
    """Simulates Streamlit UploadedFile with name and size attributes."""
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name
        self.size = len(data)


def test_get_supported_formats():
    formats = get_supported_formats()
    assert ".csv" in formats
    assert ".xlsx" in formats
    assert ".tsv" in formats


def test_validate_file_source_valid_csv():
    info = validate_file_source("data.csv")
    assert info["is_valid"] is True
    assert info["format"] == "csv"
    assert info["file_name"] == "data.csv"


def test_validate_file_source_valid_excel():
    info = validate_file_source("sheet.xlsx")
    assert info["is_valid"] is True
    assert info["format"] == "excel"


def test_validate_file_source_invalid_format():
    with pytest.raises(InvalidFileFormatError):
        validate_file_source("document.pdf")


def test_validate_file_source_none():
    with pytest.raises(DataFixUploadError):
        validate_file_source(None)


def test_load_csv_from_path(tmp_path):
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("id,name,score\n1,Alice,95\n2,Bob,88\n", encoding="utf-8")

    df = load_csv(str(csv_path))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["id", "name", "score"]
    assert df.iloc[0]["name"] == "Alice"


def test_load_csv_from_bytes_io():
    csv_bytes = b"id,val\n1,100\n2,200\n"
    buffer = DummyStreamlitFile(csv_bytes, name="data.csv")

    df = load_dataset(buffer)
    assert len(df) == 2
    assert "val" in df.columns
    # Verify buffer position was reset
    assert buffer.tell() == 0


def test_load_tsv():
    tsv_bytes = b"id\tcity\n1\tNew York\n2\tLondon\n"
    buffer = DummyStreamlitFile(tsv_bytes, name="locations.tsv")

    df = load_dataset(buffer)
    assert len(df) == 2
    assert list(df.columns) == ["id", "city"]


def test_load_excel_from_bytes_io():
    # Create an in-memory excel file
    output = io.BytesIO()
    sample_df = pd.DataFrame({"product": ["A", "B", "C"], "price": [10.5, 20.0, 15.75]})
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sample_df.to_excel(writer, index=False, sheet_name="Products")
    excel_bytes = output.getvalue()

    buffer = DummyStreamlitFile(excel_bytes, name="catalog.xlsx")
    df = load_dataset(buffer)
    assert len(df) == 3
    assert list(df.columns) == ["product", "price"]
    assert df.iloc[1]["product"] == "B"


def test_empty_csv_file_zero_bytes(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    with pytest.raises(EmptyFileError):
        load_csv(str(empty_csv))


def test_empty_csv_buffer_zero_bytes():
    buffer = DummyStreamlitFile(b"", name="empty.csv")
    with pytest.raises(EmptyFileError):
        load_dataset(buffer)


def test_csv_headers_only(tmp_path):
    header_only_csv = tmp_path / "headers_only.csv"
    header_only_csv.write_text("col1,col2,col3\n", encoding="utf-8")

    with pytest.raises(EmptyFileError) as exc_info:
        load_csv(str(header_only_csv))
    assert "no data rows" in str(exc_info.value)


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_dataset("non_existent_file_path_12345.csv")


def test_corrupted_csv():
    # Mismatched rows causing parser error when strict
    corrupt_data = b"col1,col2\nval1\nval1,val2,val3\n"
    buffer = DummyStreamlitFile(corrupt_data, name="corrupt.csv")
    with pytest.raises(FileParsingError):
        load_csv(buffer, on_bad_lines="error")


def test_unified_load_dataset_with_explicit_format():
    csv_bytes = b"x,y\n10,20\n30,40\n"
    # nameless buffer
    buffer = io.BytesIO(csv_bytes)
    df = load_dataset(buffer, file_format="csv")
    assert len(df) == 2
    assert "x" in df.columns


def test_latin1_encoding_fallback():
    # Character 0xE9 is 'é' in Latin-1 which is invalid standalone in UTF-8
    latin1_bytes = b"city,temperature\nMontr\xe9al,22\n"
    buffer = DummyStreamlitFile(latin1_bytes, name="weather.csv")
    df = load_dataset(buffer)
    assert len(df) == 1
    assert "Montréal" in df.iloc[0]["city"] or "Montr" in df.iloc[0]["city"]


def test_excel_multi_sheet():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame({"s1_col": [1, 2]}).to_excel(writer, index=False, sheet_name="SheetA")
        pd.DataFrame({"s2_col": [10, 20]}).to_excel(writer, index=False, sheet_name="SheetB")

    buffer = DummyStreamlitFile(output.getvalue(), name="multisheet.xlsx")
    df_sheet_b = load_excel(buffer, sheet_name="SheetB")
    assert "s2_col" in df_sheet_b.columns
    assert len(df_sheet_b) == 2
