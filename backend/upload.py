"""Dataset Upload and Validation Module for DataFix Engine.

This module provides robust loading, validation, and error-handling utilities
for ingesting tabular datasets (CSV and Excel formats) into Pandas DataFrames.
It supports both local file paths and in-memory file buffers (such as Streamlit UploadedFile).
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, TextIO, Union

import pandas as pd


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DataFixUploadError(Exception):
    """Base exception for all upload and ingestion errors in DataFix."""
    pass


class InvalidFileFormatError(DataFixUploadError):
    """Raised when an unsupported file format or extension is provided."""
    pass


class EmptyFileError(DataFixUploadError):
    """Raised when the uploaded file is empty or contains no data rows."""
    pass


class FileParsingError(DataFixUploadError):
    """Raised when a file cannot be parsed or read into a DataFrame."""
    pass


# ---------------------------------------------------------------------------
# Supported Formats
# ---------------------------------------------------------------------------

SUPPORTED_CSV_EXTENSIONS = {".csv", ".tsv", ".txt"}
SUPPORTED_EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb"}
SUPPORTED_EXTENSIONS = SUPPORTED_CSV_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS


def get_supported_formats() -> List[str]:
    """Return a sorted list of supported file format extensions."""
    return sorted(list(SUPPORTED_EXTENSIONS))


# ---------------------------------------------------------------------------
# File Validation & Format Detection Helpers
# ---------------------------------------------------------------------------

def _extract_filename(source: Any) -> Optional[str]:
    """Extract filename from a file path or file-like buffer object."""
    if isinstance(source, (str, Path)):
        return Path(source).name
    if hasattr(source, "name") and isinstance(source.name, str):
        return Path(source.name).name
    return None


def _detect_format(source: Any, explicit_format: Optional[str] = None) -> str:
    """Detect format ('csv' or 'excel') from source filename or explicit override."""
    if explicit_format:
        fmt = explicit_format.strip().lower().lstrip(".")
        if fmt in {"csv", "tsv", "txt"}:
            return "csv"
        if fmt in {"xlsx", "xls", "xlsm", "xlsb", "excel"}:
            return "excel"
        raise InvalidFileFormatError(
            f"Unsupported explicit format: '{explicit_format}'. "
            f"Supported formats are: {', '.join(get_supported_formats())}"
        )

    filename = _extract_filename(source)
    if not filename:
        raise InvalidFileFormatError(
            "Could not determine file format from input source. "
            "Please provide a filename or specify the format explicitly (e.g., 'csv' or 'excel')."
        )

    ext = Path(filename).suffix.lower()
    if not ext:
        raise InvalidFileFormatError(
            f"File '{filename}' does not have an extension. "
            f"Supported formats are: {', '.join(get_supported_formats())}"
        )

    if ext in SUPPORTED_CSV_EXTENSIONS:
        return "csv"
    if ext in SUPPORTED_EXCEL_EXTENSIONS:
        return "excel"

    raise InvalidFileFormatError(
        f"Unsupported file format '{ext}' for file '{filename}'. "
        f"Supported formats are: {', '.join(get_supported_formats())}"
    )


def _check_empty_buffer(source: Any) -> int:
    """Check if the source file or buffer is empty (0 bytes). Returns size in bytes."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {source}")
        if not path.is_file():
            raise FileParsingError(f"Provided path is not a file: {source}")
        size = path.stat().st_size
        if size == 0:
            raise EmptyFileError(f"The file '{path.name}' is empty (0 bytes).")
        return size

    # Handle Streamlit UploadedFile or file-like objects (BytesIO, StringIO, etc.)
    if hasattr(source, "size") and isinstance(source.size, int):
        if source.size == 0:
            name = _extract_filename(source) or "Uploaded file"
            raise EmptyFileError(f"The uploaded file '{name}' is empty (0 bytes).")
        return source.size

    if hasattr(source, "seek") and hasattr(source, "tell"):
        current_pos = source.tell()
        source.seek(0, os.SEEK_END)
        size = source.tell()
        source.seek(current_pos)
        if size == 0:
            name = _extract_filename(source) or "Buffer"
            raise EmptyFileError(f"The input buffer '{name}' is empty (0 bytes).")
        return size

    return -1


def _reset_buffer(source: Any) -> None:
    """Safely reset buffer read pointer to 0 if supported."""
    if hasattr(source, "seek"):
        try:
            source.seek(0)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public Validation Function
# ---------------------------------------------------------------------------

def validate_file_source(
    source: Any,
    file_format: Optional[str] = None,
    check_exists: bool = False,
) -> Dict[str, Any]:
    """Validate a dataset source (path, filename, or buffer) before loading.

    Parameters
    ----------
    source : Union[str, Path, BinaryIO, TextIO, Any]
        The file path, filename string, or file-like object (e.g. Streamlit UploadedFile).
    file_format : Optional[str]
        Optional format override ('csv', 'excel', etc.).
    check_exists : bool, default False
        Whether to require that a path string exists on disk. If False and the path
        does not exist, format and name are validated without raising FileNotFoundError.

    Returns
    -------
    Dict[str, Any]
        Validation summary containing filename, detected format, size in bytes, and status.

    Raises
    ------
    DataFixUploadError
        If validation fails due to empty file, invalid format, or missing file.
    """
    if source is None:
        raise DataFixUploadError("No file source provided (source is None).")

    detected_format = _detect_format(source, explicit_format=file_format)

    size_bytes: Optional[int] = None
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists():
            size_bytes = _check_empty_buffer(source)
        elif check_exists:
            raise FileNotFoundError(f"File not found: {source}")
    else:
        size_bytes = _check_empty_buffer(source)

    filename = _extract_filename(source) or "unnamed_dataset"

    return {
        "file_name": filename,
        "format": detected_format,
        "size_bytes": size_bytes,
        "is_valid": True,
    }


# ---------------------------------------------------------------------------
# Loading Functions
# ---------------------------------------------------------------------------

def load_csv(
    source: Union[str, Path, BinaryIO, TextIO, Any],
    **kwargs: Any
) -> pd.DataFrame:
    """Load a CSV, TSV, or delimited text file into a Pandas DataFrame.

    Parameters
    ----------
    source : Union[str, Path, BinaryIO, TextIO, Any]
        Path to the file or a file-like buffer object.
    **kwargs : Any
        Additional keyword arguments forwarded to `pd.read_csv`.

    Returns
    -------
    pd.DataFrame
        Loaded Pandas DataFrame.

    Raises
    ------
    EmptyFileError
        If the file has 0 bytes or contains no rows.
    FileParsingError
        If the file cannot be parsed or decoded.
    """
    _check_empty_buffer(source)
    _reset_buffer(source)

    # Determine default delimiter if tsv
    filename = _extract_filename(source)
    if filename and filename.lower().endswith(".tsv") and "sep" not in kwargs and "delimiter" not in kwargs:
        kwargs["sep"] = "\t"

    encodings_to_try = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    user_encoding = kwargs.pop("encoding", None)
    if user_encoding:
        encodings_to_try.insert(0, user_encoding)

    df: Optional[pd.DataFrame] = None
    last_error: Optional[Exception] = None

    for enc in encodings_to_try:
        _reset_buffer(source)
        try:
            df = pd.read_csv(source, encoding=enc, **kwargs)
            break
        except pd.errors.EmptyDataError as err:
            raise EmptyFileError("The file does not contain any readable columns or data.") from err
        except (UnicodeDecodeError, LookupError) as err:
            last_error = err
            continue
        except (pd.errors.ParserError, ValueError) as err:
            raise FileParsingError(f"Failed to parse CSV file: {err}") from err
        except Exception as err:
            raise FileParsingError(f"Unexpected error while reading CSV: {err}") from err
        finally:
            _reset_buffer(source)

    if df is None:
        raise FileParsingError(
            f"Unable to decode CSV file with attempted encodings ({', '.join(encodings_to_try)}). "
            f"Details: {last_error}"
        )

    if df.empty:
        if len(df.columns) == 0:
            raise EmptyFileError("The CSV file is empty and contains no headers or rows.")
        raise EmptyFileError("The CSV file contains column headers but no data rows.")

    return df


def load_excel(
    source: Union[str, Path, BinaryIO, Any],
    sheet_name: Union[str, int, None] = 0,
    **kwargs: Any
) -> pd.DataFrame:
    """Load an Excel spreadsheet (.xlsx, .xls) into a Pandas DataFrame.

    Parameters
    ----------
    source : Union[str, Path, BinaryIO, Any]
        Path to the file or a file-like buffer object.
    sheet_name : Union[str, int, None], default 0
        Name or 0-indexed position of the sheet to load.
    **kwargs : Any
        Additional keyword arguments forwarded to `pd.read_excel`.

    Returns
    -------
    pd.DataFrame
        Loaded Pandas DataFrame.

    Raises
    ------
    EmptyFileError
        If the worksheet is empty or contains no data rows.
    FileParsingError
        If the file cannot be opened or parsed.
    """
    _check_empty_buffer(source)
    _reset_buffer(source)

    if "engine" not in kwargs:
        filename = _extract_filename(source)
        if filename and filename.lower().endswith((".xlsx", ".xlsm")):
            kwargs["engine"] = "openpyxl"

    try:
        df = pd.read_excel(source, sheet_name=sheet_name, **kwargs)
    except pd.errors.EmptyDataError as err:
        raise EmptyFileError("The Excel sheet contains no readable columns or data.") from err
    except (ValueError, KeyError) as err:
        raise FileParsingError(f"Invalid Excel sheet or content: {err}") from err
    except Exception as err:
        raise FileParsingError(f"Failed to load Excel file: {err}") from err
    finally:
        _reset_buffer(source)

    if isinstance(df, dict):
        # In case sheet_name=None was passed, returning a dict of DataFrames
        if not df:
            raise EmptyFileError("The Excel workbook contains no sheets.")
        first_sheet = next(iter(df.values()))
        df = first_sheet

    if df.empty:
        if len(df.columns) == 0:
            raise EmptyFileError("The Excel sheet is empty and contains no headers or rows.")
        raise EmptyFileError("The Excel sheet contains column headers but no data rows.")

    return df


def load_dataset(
    source: Union[str, Path, BinaryIO, TextIO, Any],
    file_format: Optional[str] = None,
    **kwargs: Any
) -> pd.DataFrame:
    """Unified entrypoint to load a dataset from CSV or Excel into a Pandas DataFrame.

    Validates file format, checks for empty contents, handles encoding, and
    returns a clean Pandas DataFrame ready for profiling and quality checks.

    Parameters
    ----------
    source : Union[str, Path, BinaryIO, TextIO, Any]
        File path string, Path object, or file-like buffer (e.g. Streamlit UploadedFile).
    file_format : Optional[str]
        Explicit format specifier ('csv' or 'excel'). If None, inferred automatically.
    **kwargs : Any
        Additional keyword arguments passed to the underlying loader function
        (`load_csv` or `load_excel`).

    Returns
    -------
    pd.DataFrame
        Loaded dataset as a Pandas DataFrame.

    Raises
    ------
    DataFixUploadError
        If the input is invalid, format is unsupported, file is empty, or parsing fails.
    """
    validation_info = validate_file_source(source, file_format=file_format, check_exists=True)
    fmt = validation_info["format"]

    if fmt == "csv":
        return load_csv(source, **kwargs)
    elif fmt == "excel":
        return load_excel(source, **kwargs)
    else:
        raise InvalidFileFormatError(f"Unsupported format handler for '{fmt}'.")
