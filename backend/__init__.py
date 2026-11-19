"""DataFix Backend Package.

This package provides data ingestion, validation, and profiling utilities
for the DataFix Autonomous Data Quality Engine.
"""

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

from backend.profiling import (
    profile_dataset,
    get_dataset_overview,
    get_column_types,
    get_missing_values,
    get_duplicate_summary,
    get_unique_values,
    get_numerical_summary,
    get_categorical_summary,
    get_data_quality_summary,
)

from backend.cleaning import (
    handle_missing_values,
    handle_duplicates,
    handle_outliers,
    clean_text_columns,
    cast_column_types,
    CleaningPipeline,
    AuditLogEntry,
    DataFixCleaningError,
    InvalidStrategyError,
    ColumnNotFoundError,
)

__all__ = [
    # Upload & Ingestion
    "load_dataset",
    "load_csv",
    "load_excel",
    "validate_file_source",
    "get_supported_formats",
    "DataFixUploadError",
    "InvalidFileFormatError",
    "EmptyFileError",
    "FileParsingError",
    # Profiling & Quality
    "profile_dataset",
    "get_dataset_overview",
    "get_column_types",
    "get_missing_values",
    "get_duplicate_summary",
    "get_unique_values",
    "get_numerical_summary",
    "get_categorical_summary",
    "get_data_quality_summary",
    # Cleaning & Remediation
    "handle_missing_values",
    "handle_duplicates",
    "handle_outliers",
    "clean_text_columns",
    "cast_column_types",
    "CleaningPipeline",
    "AuditLogEntry",
    "DataFixCleaningError",
    "InvalidStrategyError",
    "ColumnNotFoundError",
]
