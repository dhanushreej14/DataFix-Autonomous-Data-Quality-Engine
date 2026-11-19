"""Data Cleaning and Remediation Engine for DataFix Engine.

This module provides deterministic, non-destructive data transformation primitives,
including missing value imputation, deduplication, outlier clipping/filtering,
text normalization, and type casting, accompanied by a comprehensive audit logging system.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DataFixCleaningError(Exception):
    """Base exception for all cleaning and transformation errors in DataFix."""
    pass


class InvalidStrategyError(DataFixCleaningError):
    """Raised when an unsupported transformation strategy or method is requested."""
    pass


class ColumnNotFoundError(DataFixCleaningError):
    """Raised when a specified column does not exist in the DataFrame."""
    pass


# ---------------------------------------------------------------------------
# Audit Log Data Structures
# ---------------------------------------------------------------------------

class AuditLogEntry:
    """Represents a single atomic data transformation audit record."""

    def __init__(
        self,
        step: int,
        operation: str,
        columns: Sequence[str],
        strategy: str,
        parameters: Dict[str, Any],
        rows_before: int,
        rows_after: int,
        rows_affected: int,
        details: str,
        timestamp: Optional[str] = None,
    ) -> None:
        self.step = step
        self.operation = operation
        self.columns = list(columns)
        self.strategy = strategy
        self.parameters = parameters
        self.rows_before = rows_before
        self.rows_after = rows_after
        self.rows_affected = rows_affected
        self.details = details
        self.timestamp = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log entry to a JSON-serializable dictionary."""
        return {
            "step": self.step,
            "operation": self.operation,
            "columns": self.columns,
            "strategy": self.strategy,
            "parameters": self.parameters,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_affected": self.rows_affected,
            "details": self.details,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"<AuditLogEntry step={self.step} op='{self.operation}' "
            f"strategy='{self.strategy}' affected={self.rows_affected}>"
        )


# ---------------------------------------------------------------------------
# Validation Helper Functions
# ---------------------------------------------------------------------------

def _validate_dataframe(df: Any) -> pd.DataFrame:
    """Validate that input is a valid pandas DataFrame."""
    if df is None:
        raise ValueError("Input DataFrame cannot be None.")
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas.DataFrame, got {type(df).__name__}.")
    return df


def _check_columns_exist(df: pd.DataFrame, columns: Sequence[str]) -> None:
    """Validate that all requested columns exist in DataFrame."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ColumnNotFoundError(
            f"Column(s) {missing} not found in DataFrame. Available columns: {list(df.columns)}"
        )


def _count_series_diff(s1: pd.Series, s2: pd.Series) -> int:
    """Safely count differing elements between two series regardless of underlying dtypes."""
    both_na = s1.isna() & s2.isna()
    diff = ~both_na & (s1.astype(str) != s2.astype(str))
    return int(diff.sum())


# ---------------------------------------------------------------------------
# 1. Missing Value Remediation
# ---------------------------------------------------------------------------

SUPPORTED_IMPUTATION_STRATEGIES = {
    "mean", "median", "mode", "constant",
    "forward_fill", "backward_fill", "drop_rows", "drop_column"
}


def handle_missing_values(
    df: pd.DataFrame,
    columns: Optional[Union[str, Sequence[str]]] = None,
    strategy: str = "mean",
    fill_value: Optional[Any] = None,
    step: int = 1,
) -> Tuple[pd.DataFrame, AuditLogEntry]:
    """Impute or remove missing (null / NaN / NaT) values in specified columns.

    This function never mutates the original DataFrame and returns a new DataFrame copy.

    Parameters
    ----------
    df : pd.DataFrame
        The source dataset.
    columns : Optional[Union[str, Sequence[str]]], default None
        Column name(s) to apply the strategy to. If None, applied to all columns with missing values.
    strategy : str, default 'mean'
        One of: 'mean', 'median', 'mode', 'constant', 'forward_fill', 'backward_fill',
        'drop_rows', 'drop_column'.
    fill_value : Optional[Any], default None
        Value used when strategy is 'constant'. Required if strategy == 'constant'.
    step : int, default 1
        Sequence step index for the audit log entry.

    Returns
    -------
    Tuple[pd.DataFrame, AuditLogEntry]
        Cleaned DataFrame copy and the corresponding audit log entry.
    """
    _validate_dataframe(df)
    clean_df = df.copy()
    rows_before = len(clean_df)

    strat = strategy.lower().strip()
    if strat not in SUPPORTED_IMPUTATION_STRATEGIES:
        raise InvalidStrategyError(
            f"Unsupported strategy '{strategy}'. Supported strategies: {sorted(list(SUPPORTED_IMPUTATION_STRATEGIES))}"
        )

    # Determine target columns
    if columns is None:
        target_cols = [col for col in clean_df.columns if clean_df[col].isna().any()]
    elif isinstance(columns, str):
        target_cols = [columns]
    else:
        target_cols = list(columns)

    _check_columns_exist(clean_df, target_cols)

    if not target_cols or rows_before == 0:
        entry = AuditLogEntry(
            step=step,
            operation="handle_missing_values",
            columns=target_cols,
            strategy=strat,
            parameters={"fill_value": fill_value},
            rows_before=rows_before,
            rows_after=rows_before,
            rows_affected=0,
            details="No missing values found or target column list is empty.",
        )
        return clean_df, entry

    total_imputed_cells = 0

    if strat == "drop_rows":
        mask_missing = clean_df[target_cols].isna().any(axis=1)
        rows_affected = int(mask_missing.sum())
        clean_df = clean_df[~mask_missing].reset_index(drop=True)
        rows_after = len(clean_df)
        details = f"Dropped {rows_affected} row(s) containing missing values across column(s): {target_cols}."

    elif strat == "drop_column":
        rows_affected = 0
        clean_df = clean_df.drop(columns=target_cols)
        rows_after = len(clean_df)
        details = f"Dropped column(s): {target_cols}."

    elif strat == "constant":
        if fill_value is None:
            raise ValueError("fill_value cannot be None when using the 'constant' imputation strategy.")
        for col in target_cols:
            col_missing = int(clean_df[col].isna().sum())
            if col_missing > 0:
                clean_df[col] = clean_df[col].fillna(fill_value)
                total_imputed_cells += col_missing
        rows_after = len(clean_df)
        rows_affected = total_imputed_cells
        details = f"Imputed {total_imputed_cells} missing cell(s) with constant value '{fill_value}'."

    elif strat in {"mean", "median"}:
        for col in target_cols:
            if not pd.api.types.is_numeric_dtype(clean_df[col]):
                raise InvalidStrategyError(
                    f"Strategy '{strat}' requires numeric column, but '{col}' has dtype '{clean_df[col].dtype}'."
                )
            col_missing = int(clean_df[col].isna().sum())
            if col_missing > 0:
                computed_val = float(clean_df[col].mean()) if strat == "mean" else float(clean_df[col].median())
                if pd.isna(computed_val):
                    continue  # All values were NaN
                clean_df[col] = clean_df[col].fillna(computed_val)
                total_imputed_cells += col_missing
        rows_after = len(clean_df)
        rows_affected = total_imputed_cells
        details = f"Imputed {total_imputed_cells} missing cell(s) using column {strat}."

    elif strat == "mode":
        for col in target_cols:
            col_missing = int(clean_df[col].isna().sum())
            if col_missing > 0:
                mode_series = clean_df[col].mode(dropna=True)
                if not mode_series.empty:
                    mode_val = mode_series.iloc[0]
                    clean_df[col] = clean_df[col].fillna(mode_val)
                    total_imputed_cells += col_missing
        rows_after = len(clean_df)
        rows_affected = total_imputed_cells
        details = f"Imputed {total_imputed_cells} missing cell(s) using column mode."

    elif strat == "forward_fill":
        for col in target_cols:
            col_missing = int(clean_df[col].isna().sum())
            if col_missing > 0:
                clean_df[col] = clean_df[col].ffill()
                filled_count = col_missing - int(clean_df[col].isna().sum())
                total_imputed_cells += filled_count
        rows_after = len(clean_df)
        rows_affected = total_imputed_cells
        details = f"Imputed {total_imputed_cells} cell(s) using forward-fill."

    elif strat == "backward_fill":
        for col in target_cols:
            col_missing = int(clean_df[col].isna().sum())
            if col_missing > 0:
                clean_df[col] = clean_df[col].bfill()
                filled_count = col_missing - int(clean_df[col].isna().sum())
                total_imputed_cells += filled_count
        rows_after = len(clean_df)
        rows_affected = total_imputed_cells
        details = f"Imputed {total_imputed_cells} cell(s) using backward-fill."

    entry = AuditLogEntry(
        step=step,
        operation="handle_missing_values",
        columns=target_cols,
        strategy=strat,
        parameters={"fill_value": fill_value},
        rows_before=rows_before,
        rows_after=rows_after,
        rows_affected=rows_affected,
        details=details,
    )
    return clean_df, entry


# ---------------------------------------------------------------------------
# 2. Duplicate Row Remediation
# ---------------------------------------------------------------------------

SUPPORTED_DUPLICATE_STRATEGIES = {"drop_first", "drop_last", "drop_all"}


def handle_duplicates(
    df: pd.DataFrame,
    subset: Optional[Union[str, Sequence[str]]] = None,
    strategy: str = "drop_first",
    step: int = 1,
) -> Tuple[pd.DataFrame, AuditLogEntry]:
    """Detect and remove duplicate rows based on all or a subset of columns.

    Parameters
    ----------
    df : pd.DataFrame
        The source dataset.
    subset : Optional[Union[str, Sequence[str]]], default None
        Column name or list of column names defining row uniqueness. If None, considers all columns.
    strategy : str, default 'drop_first'
        One of: 'drop_first' (keep first occurrence), 'drop_last' (keep last occurrence),
        or 'drop_all' (remove all duplicate occurrences).
    step : int, default 1
        Sequence step index for the audit log entry.

    Returns
    -------
    Tuple[pd.DataFrame, AuditLogEntry]
        Cleaned DataFrame copy and the corresponding audit log entry.
    """
    _validate_dataframe(df)
    clean_df = df.copy()
    rows_before = len(clean_df)

    strat = strategy.lower().strip()
    if strat not in SUPPORTED_DUPLICATE_STRATEGIES:
        raise InvalidStrategyError(
            f"Unsupported duplicate strategy '{strategy}'. Supported strategies: {sorted(list(SUPPORTED_DUPLICATE_STRATEGIES))}"
        )

    target_subset: Optional[List[str]] = None
    if subset is not None:
        target_subset = [subset] if isinstance(subset, str) else list(subset)
        _check_columns_exist(clean_df, target_subset)

    if rows_before == 0:
        entry = AuditLogEntry(
            step=step,
            operation="handle_duplicates",
            columns=target_subset or list(clean_df.columns),
            strategy=strat,
            parameters={"subset": target_subset},
            rows_before=0,
            rows_after=0,
            rows_affected=0,
            details="Dataset is empty; no duplicates to remove.",
        )
        return clean_df, entry

    if strat == "drop_first":
        keep: Union[str, bool] = "first"
    elif strat == "drop_last":
        keep = "last"
    else:  # drop_all
        keep = False

    dup_mask = clean_df.duplicated(subset=target_subset, keep=keep)
    rows_affected = int(dup_mask.sum())
    clean_df = clean_df[~dup_mask].reset_index(drop=True)
    rows_after = len(clean_df)

    details = (
        f"Removed {rows_affected} duplicate row(s) using strategy '{strat}' "
        f"on {'subset ' + str(target_subset) if target_subset else 'all columns'}."
    )

    entry = AuditLogEntry(
        step=step,
        operation="handle_duplicates",
        columns=target_subset or list(df.columns),
        strategy=strat,
        parameters={"subset": target_subset},
        rows_before=rows_before,
        rows_after=rows_after,
        rows_affected=rows_affected,
        details=details,
    )
    return clean_df, entry


# ---------------------------------------------------------------------------
# 3. Outlier Remediation
# ---------------------------------------------------------------------------

SUPPORTED_OUTLIER_METHODS = {"iqr", "zscore"}
SUPPORTED_OUTLIER_STRATEGIES = {"clip", "drop", "set_null"}


def handle_outliers(
    df: pd.DataFrame,
    columns: Optional[Union[str, Sequence[str]]] = None,
    method: str = "iqr",
    strategy: str = "clip",
    factor: float = 1.5,
    step: int = 1,
) -> Tuple[pd.DataFrame, AuditLogEntry]:
    """Detect and remediate numerical outliers via IQR or Z-score thresholds.

    Parameters
    ----------
    df : pd.DataFrame
        The source dataset.
    columns : Optional[Union[str, Sequence[str]]], default None
        Numerical column name(s) to inspect. If None, applied to all numerical columns.
    method : str, default 'iqr'
        Detection method: 'iqr' (Tukey's IQR method) or 'zscore' (standard deviations).
    strategy : str, default 'clip'
        Remediation strategy: 'clip' (Winsorize to boundary thresholds),
        'drop' (remove rows containing outliers), or 'set_null' (replace outliers with NaN).
    factor : float, default 1.5
        Multiplier for IQR (typically 1.5 for moderate, 3.0 for extreme) or Z-score threshold (typically 3.0).
    step : int, default 1
        Sequence step index for the audit log entry.

    Returns
    -------
    Tuple[pd.DataFrame, AuditLogEntry]
        Cleaned DataFrame copy and the corresponding audit log entry.
    """
    _validate_dataframe(df)
    clean_df = df.copy()
    rows_before = len(clean_df)

    m = method.lower().strip()
    strat = strategy.lower().strip()

    if m not in SUPPORTED_OUTLIER_METHODS:
        raise InvalidStrategyError(
            f"Unsupported outlier detection method '{method}'. Supported methods: {sorted(list(SUPPORTED_OUTLIER_METHODS))}"
        )
    if strat not in SUPPORTED_OUTLIER_STRATEGIES:
        raise InvalidStrategyError(
            f"Unsupported outlier strategy '{strategy}'. Supported strategies: {sorted(list(SUPPORTED_OUTLIER_STRATEGIES))}"
        )

    # Determine target columns (must be numerical)
    if columns is None:
        target_cols = [c for c in clean_df.columns if pd.api.types.is_numeric_dtype(clean_df[c])]
    elif isinstance(columns, str):
        target_cols = [columns]
    else:
        target_cols = list(columns)

    _check_columns_exist(clean_df, target_cols)

    # Validate all target columns are numerical
    non_numeric = [c for c in target_cols if not pd.api.types.is_numeric_dtype(clean_df[c])]
    if non_numeric:
        raise InvalidStrategyError(
            f"Outlier handling only applies to numeric columns. Non-numeric column(s): {non_numeric}"
        )

    if not target_cols or rows_before == 0:
        entry = AuditLogEntry(
            step=step,
            operation="handle_outliers",
            columns=target_cols,
            strategy=f"{m}_{strat}",
            parameters={"method": m, "strategy": strat, "factor": factor},
            rows_before=rows_before,
            rows_after=rows_before,
            rows_affected=0,
            details="No numerical target columns or dataset is empty.",
        )
        return clean_df, entry

    outlier_rows_mask = pd.Series(False, index=clean_df.index)
    total_outliers_modified = 0
    bounds_summary: Dict[str, Dict[str, float]] = {}

    for col in target_cols:
        series = clean_df[col].dropna()
        if len(series) < 3:
            continue

        if m == "iqr":
            q25 = float(series.quantile(0.25))
            q75 = float(series.quantile(0.75))
            iqr = q75 - q25
            lower_bound = q25 - (factor * iqr)
            upper_bound = q75 + (factor * iqr)
        else:  # zscore
            mean = float(series.mean())
            std = float(series.std())
            if std == 0.0:
                continue
            lower_bound = mean - (factor * std)
            upper_bound = mean + (factor * std)

        bounds_summary[col] = {"lower": round(lower_bound, 4), "upper": round(upper_bound, 4)}
        col_outlier_mask = (clean_df[col] < lower_bound) | (clean_df[col] > upper_bound)
        outlier_count = int(col_outlier_mask.sum())

        if outlier_count > 0:
            outlier_rows_mask = outlier_rows_mask | col_outlier_mask

            if strat == "clip":
                clean_df[col] = clean_df[col].clip(lower=lower_bound, upper=upper_bound)
                total_outliers_modified += outlier_count
            elif strat == "set_null":
                clean_df.loc[col_outlier_mask, col] = np.nan
                total_outliers_modified += outlier_count

    if strat == "drop":
        rows_affected = int(outlier_rows_mask.sum())
        clean_df = clean_df[~outlier_rows_mask].reset_index(drop=True)
        rows_after = len(clean_df)
        details = (
            f"Dropped {rows_affected} row(s) containing outliers using '{m}' method "
            f"(factor={factor}) across columns: {target_cols}."
        )
    else:
        rows_affected = total_outliers_modified
        rows_after = len(clean_df)
        details = (
            f"Applied '{strat}' to {total_outliers_modified} outlier value(s) using '{m}' method "
            f"(factor={factor}) across columns: {target_cols}."
        )

    entry = AuditLogEntry(
        step=step,
        operation="handle_outliers",
        columns=target_cols,
        strategy=f"{m}_{strat}",
        parameters={"method": m, "strategy": strat, "factor": factor, "bounds": bounds_summary},
        rows_before=rows_before,
        rows_after=rows_after,
        rows_affected=rows_affected,
        details=details,
    )
    return clean_df, entry


# ---------------------------------------------------------------------------
# 4. Text & Categorical Standardization
# ---------------------------------------------------------------------------

SUPPORTED_CASE_STRATEGIES = {"lower", "upper", "title", None}


def clean_text_columns(
    df: pd.DataFrame,
    columns: Optional[Union[str, Sequence[str]]] = None,
    strip_whitespace: bool = True,
    case: Optional[str] = None,
    remove_special_chars: bool = False,
    replace_empty_with_nan: bool = True,
    step: int = 1,
) -> Tuple[pd.DataFrame, AuditLogEntry]:
    """Standardize string formatting, whitespace, casing, and empty strings.

    Parameters
    ----------
    df : pd.DataFrame
        The source dataset.
    columns : Optional[Union[str, Sequence[str]]], default None
        Text column name(s) to standardize. If None, applied to all object/string columns.
    strip_whitespace : bool, default True
        Whether to strip leading, trailing, and redundant consecutive whitespace.
    case : Optional[str], default None
        Casing transformation: 'lower', 'upper', 'title', or None to leave casing as-is.
    remove_special_chars : bool, default False
        Whether to strip non-alphanumeric characters (keeps letters, numbers, and single spaces).
    replace_empty_with_nan : bool, default True
        Whether to convert empty strings or whitespace-only strings to NaN.
    step : int, default 1
        Sequence step index for the audit log entry.

    Returns
    -------
    Tuple[pd.DataFrame, AuditLogEntry]
        Cleaned DataFrame copy and the corresponding audit log entry.
    """
    _validate_dataframe(df)
    clean_df = df.copy()
    rows_before = len(clean_df)

    if case is not None and case.lower().strip() not in {"lower", "upper", "title"}:
        raise InvalidStrategyError(
            f"Unsupported case strategy '{case}'. Supported options: 'lower', 'upper', 'title', or None."
        )

    # Determine target columns (object, category, string)
    if columns is None:
        target_cols = [
            c for c in clean_df.columns
            if pd.api.types.is_string_dtype(clean_df[c]) or clean_df[c].dtype == "object"
        ]
    elif isinstance(columns, str):
        target_cols = [columns]
    else:
        target_cols = list(columns)

    _check_columns_exist(clean_df, target_cols)

    if not target_cols or rows_before == 0:
        entry = AuditLogEntry(
            step=step,
            operation="clean_text_columns",
            columns=target_cols,
            strategy="text_standardization",
            parameters={
                "strip_whitespace": strip_whitespace,
                "case": case,
                "remove_special_chars": remove_special_chars,
                "replace_empty_with_nan": replace_empty_with_nan,
            },
            rows_before=rows_before,
            rows_after=rows_before,
            rows_affected=0,
            details="No text columns found or dataset is empty.",
        )
        return clean_df, entry

    total_cells_modified = 0

    for col in target_cols:
        original_series = clean_df[col].copy()

        def _clean_str(val: Any) -> Any:
            if pd.isna(val) or val is None:
                return np.nan

            s = str(val)

            # Strip whitespace
            if strip_whitespace:
                # Collapse internal multiple whitespaces and strip boundaries
                s = re.sub(r"\s+", " ", s).strip()

            # Remove special characters if requested (keep alphanumeric, space, underscore, hyphen)
            if remove_special_chars:
                s = re.sub(r"[^\w\s-]", "", s)
                if strip_whitespace:
                    s = re.sub(r"\s+", " ", s).strip()

            # Case transformation
            if case:
                c = case.lower().strip()
                if c == "lower":
                    s = s.lower()
                elif c == "upper":
                    s = s.upper()
                elif c == "title":
                    s = s.title()

            # Replace empty strings with NaN
            if replace_empty_with_nan and s == "":
                return np.nan

            return s

        clean_series = clean_df[col].apply(_clean_str)

        # Count modified cells
        total_cells_modified += _count_series_diff(original_series, clean_series)
        clean_df[col] = clean_series

    entry = AuditLogEntry(
        step=step,
        operation="clean_text_columns",
        columns=target_cols,
        strategy="text_standardization",
        parameters={
            "strip_whitespace": strip_whitespace,
            "case": case,
            "remove_special_chars": remove_special_chars,
            "replace_empty_with_nan": replace_empty_with_nan,
        },
        rows_before=rows_before,
        rows_after=rows_before,
        rows_affected=total_cells_modified,
        details=f"Standardized text in {len(target_cols)} column(s); modified {total_cells_modified} cell(s).",
    )
    return clean_df, entry


# ---------------------------------------------------------------------------
# 5. Type Casting & Coercion
# ---------------------------------------------------------------------------

SUPPORTED_TARGET_TYPES = {
    "numeric", "float", "int", "datetime", "string", "category", "boolean", "bool"
}

_BOOL_TRUE_VALUES = {"true", "1", "t", "yes", "y"}
_BOOL_FALSE_VALUES = {"false", "0", "f", "no", "n"}


def cast_column_types(
    df: pd.DataFrame,
    type_map: Dict[str, str],
    clean_numeric_strings: bool = True,
    datetime_format: Optional[str] = None,
    step: int = 1,
) -> Tuple[pd.DataFrame, AuditLogEntry]:
    """Safely coerce column data types with graceful fallback for invalid values.

    Parameters
    ----------
    df : pd.DataFrame
        The source dataset.
    type_map : Dict[str, str]
        Dictionary mapping column names to target types:
        'numeric', 'float', 'int', 'datetime', 'string', 'category', 'boolean'.
    clean_numeric_strings : bool, default True
        If True, strips currency signs ($, €, £), commas, and percentage signs before numeric conversion.
    datetime_format : Optional[str], default None
        Optional strftime format string (e.g. '%Y-%m-%d') passed to `pd.to_datetime`.
    step : int, default 1
        Sequence step index for the audit log entry.

    Returns
    -------
    Tuple[pd.DataFrame, AuditLogEntry]
        Cleaned DataFrame copy and the corresponding audit log entry.
    """
    _validate_dataframe(df)
    clean_df = df.copy()
    rows_before = len(clean_df)

    if not isinstance(type_map, dict):
        raise TypeError(f"type_map must be a dictionary, got {type(type_map).__name__}.")

    _check_columns_exist(clean_df, list(type_map.keys()))

    total_cells_coerced = 0
    applied_types: Dict[str, str] = {}

    for col, target_type in type_map.items():
        t = str(target_type).lower().strip()
        if t not in SUPPORTED_TARGET_TYPES:
            raise InvalidStrategyError(
                f"Unsupported target type '{target_type}' for column '{col}'. "
                f"Supported types: {sorted(list(SUPPORTED_TARGET_TYPES))}"
            )

        original_series = clean_df[col].copy()

        if t == "float":
            series = clean_df[col]
            if clean_numeric_strings and (series.dtype == "object" or pd.api.types.is_string_dtype(series)):
                # Strip common formatting: commas, currency symbols, percentages
                series = series.astype(str).str.replace(r"[$,£€% ]", "", regex=True)
            clean_df[col] = pd.to_numeric(series, errors="coerce").astype(float)
            applied_types[col] = "float64"

        elif t == "numeric":
            series = clean_df[col]
            if clean_numeric_strings and (series.dtype == "object" or pd.api.types.is_string_dtype(series)):
                series = series.astype(str).str.replace(r"[$,£€% ]", "", regex=True)
            clean_df[col] = pd.to_numeric(series, errors="coerce")
            applied_types[col] = str(clean_df[col].dtype)

        elif t == "int":
            series = clean_df[col]
            if clean_numeric_strings and (series.dtype == "object" or pd.api.types.is_string_dtype(series)):
                series = series.astype(str).str.replace(r"[$,£€% ]", "", regex=True)
            num_series = pd.to_numeric(series, errors="coerce")
            # Use nullable integer dtype Int64 so NaNs don't force float conversion
            clean_df[col] = num_series.round().astype("Int64")
            applied_types[col] = "Int64"

        elif t == "datetime":
            clean_df[col] = pd.to_datetime(clean_df[col], format=datetime_format, errors="coerce")
            applied_types[col] = "datetime64[ns]"

        elif t == "string":
            clean_df[col] = clean_df[col].astype("string")
            applied_types[col] = "string"

        elif t == "category":
            clean_df[col] = clean_df[col].astype("category")
            applied_types[col] = "category"

        elif t in {"boolean", "bool"}:
            def _to_bool(val: Any) -> Any:
                if pd.isna(val) or val is None:
                    return np.nan
                if isinstance(val, (bool, np.bool_)):
                    return bool(val)
                s = str(val).lower().strip()
                if s in _BOOL_TRUE_VALUES:
                    return True
                if s in _BOOL_FALSE_VALUES:
                    return False
                return np.nan

            clean_df[col] = clean_df[col].apply(_to_bool).astype("boolean")
            applied_types[col] = "boolean"

        # Count coerced values
        total_cells_coerced += _count_series_diff(original_series, clean_df[col])

    entry = AuditLogEntry(
        step=step,
        operation="cast_column_types",
        columns=list(type_map.keys()),
        strategy="type_coercion",
        parameters={"type_map": type_map, "applied_types": applied_types},
        rows_before=rows_before,
        rows_after=rows_before,
        rows_affected=total_cells_coerced,
        details=f"Coerced types for columns: {applied_types}. Affected {total_cells_coerced} cell(s).",
    )
    return clean_df, entry


# ---------------------------------------------------------------------------
# 6. Cleaning Pipeline & Execution Coordinator
# ---------------------------------------------------------------------------

class CleaningPipeline:
    """Orchestrates sequential, repeatable cleaning transformations with audit logging.

    Maintains a working DataFrame copy and a chronological audit log.
    Guarantees immutability of the original input DataFrame.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """Initialize the pipeline with a source DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            The source dataset to clean.
        """
        _validate_dataframe(df)
        self._original_df = df.copy()
        self._current_df = df.copy()
        self._audit_log: List[AuditLogEntry] = []
        self._step_counter = 0

    @property
    def step_count(self) -> int:
        """Return the number of transformation steps applied."""
        return self._step_counter

    def handle_missing_values(
        self,
        columns: Optional[Union[str, Sequence[str]]] = None,
        strategy: str = "mean",
        fill_value: Optional[Any] = None,
    ) -> CleaningPipeline:
        """Apply missing value imputation or removal to the pipeline."""
        self._step_counter += 1
        self._current_df, entry = handle_missing_values(
            self._current_df,
            columns=columns,
            strategy=strategy,
            fill_value=fill_value,
            step=self._step_counter,
        )
        self._audit_log.append(entry)
        return self

    def handle_duplicates(
        self,
        subset: Optional[Union[str, Sequence[str]]] = None,
        strategy: str = "drop_first",
    ) -> CleaningPipeline:
        """Apply duplicate detection and removal to the pipeline."""
        self._step_counter += 1
        self._current_df, entry = handle_duplicates(
            self._current_df,
            subset=subset,
            strategy=strategy,
            step=self._step_counter,
        )
        self._audit_log.append(entry)
        return self

    def handle_outliers(
        self,
        columns: Optional[Union[str, Sequence[str]]] = None,
        method: str = "iqr",
        strategy: str = "clip",
        factor: float = 1.5,
    ) -> CleaningPipeline:
        """Apply outlier detection and clipping/filtering to the pipeline."""
        self._step_counter += 1
        self._current_df, entry = handle_outliers(
            self._current_df,
            columns=columns,
            method=method,
            strategy=strategy,
            factor=factor,
            step=self._step_counter,
        )
        self._audit_log.append(entry)
        return self

    def clean_text(
        self,
        columns: Optional[Union[str, Sequence[str]]] = None,
        strip_whitespace: bool = True,
        case: Optional[str] = None,
        remove_special_chars: bool = False,
        replace_empty_with_nan: bool = True,
    ) -> CleaningPipeline:
        """Apply text and categorical standardization to the pipeline."""
        self._step_counter += 1
        self._current_df, entry = clean_text_columns(
            self._current_df,
            columns=columns,
            strip_whitespace=strip_whitespace,
            case=case,
            remove_special_chars=remove_special_chars,
            replace_empty_with_nan=replace_empty_with_nan,
            step=self._step_counter,
        )
        self._audit_log.append(entry)
        return self

    def cast_types(
        self,
        type_map: Dict[str, str],
        clean_numeric_strings: bool = True,
        datetime_format: Optional[str] = None,
    ) -> CleaningPipeline:
        """Apply safe data type casting to the pipeline."""
        self._step_counter += 1
        self._current_df, entry = cast_column_types(
            self._current_df,
            type_map=type_map,
            clean_numeric_strings=clean_numeric_strings,
            datetime_format=datetime_format,
            step=self._step_counter,
        )
        self._audit_log.append(entry)
        return self

    def get_cleaned_df(self) -> pd.DataFrame:
        """Return the resulting cleaned DataFrame copy."""
        return self._current_df.copy()

    def get_original_df(self) -> pd.DataFrame:
        """Return a copy of the untouched original DataFrame."""
        return self._original_df.copy()

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return the chronological audit log as a list of dictionaries."""
        return [entry.to_dict() for entry in self._audit_log]

    def get_summary(self) -> Dict[str, Any]:
        """Generate a high-level summary of all executed transformations and their impact."""
        total_rows_initial = len(self._original_df)
        total_rows_final = len(self._current_df)
        total_cols_initial = len(self._original_df.columns)
        total_cols_final = len(self._current_df.columns)
        total_affected_cells_or_rows = sum(entry.rows_affected for entry in self._audit_log)

        return {
            "total_steps": self._step_counter,
            "rows_initial": total_rows_initial,
            "rows_final": total_rows_final,
            "rows_delta": total_rows_final - total_rows_initial,
            "cols_initial": total_cols_initial,
            "cols_final": total_cols_final,
            "cols_delta": total_cols_final - total_cols_initial,
            "total_affected": total_affected_cells_or_rows,
            "operations_executed": [entry.operation for entry in self._audit_log],
            "audit_log": self.get_audit_log(),
        }
