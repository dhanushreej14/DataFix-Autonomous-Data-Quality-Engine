"""DataFix Database and Persistence Layer.

This package provides relational persistence for analysis runs, profiling reports,
AI recommendations, cleaning history, and before-and-after quality comparisons using SQLite.
"""

from database.manager import (
    DatabaseManager,
    DatabaseError,
    RecordNotFoundError,
    DestructiveActionConfirmationRequiredError,
    safe_json_dumps,
    safe_json_loads,
)
from database.schema import create_schema

__all__ = [
    "DatabaseManager",
    "DatabaseError",
    "RecordNotFoundError",
    "DestructiveActionConfirmationRequiredError",
    "safe_json_dumps",
    "safe_json_loads",
    "create_schema",
]
