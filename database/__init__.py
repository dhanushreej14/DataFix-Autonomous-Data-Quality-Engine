
"""DataFix Database and Persistence Layer.

This package provides relational persistence for analysis runs, profiling
reports, AI recommendations, cleaning history, and quality comparisons
using SQLite.
"""

# Modern database manager
from database.manager import (
    DatabaseManager,
    DatabaseError,
    RecordNotFoundError,
    DestructiveActionConfirmationRequiredError,
    safe_json_dumps,
    safe_json_loads,
)

# Modern database schema
from database.schema import create_schema

# Legacy database functions (preserved for compatibility)
from .db import (
    init_db,
    get_connection,
    save_upload_details,
    save_quality_issue,
    save_repair_history,
    get_upload_history,
    display_upload_history,
    get_quality_issues,
    get_repair_history,
    display_repair_history,
    get_dataset_summary,
    display_dataset_summary,
    delete_upload,
    export_upload_to_dict,
)

__all__ = [
    # Modern database API
    "DatabaseManager",
    "DatabaseError",
    "RecordNotFoundError",
    "DestructiveActionConfirmationRequiredError",
    "safe_json_dumps",
    "safe_json_loads",
    "create_schema",

    # Legacy database API
    "init_db",
    "get_connection",
    "save_upload_details",
    "save_quality_issue",
    "save_repair_history",
    "get_upload_history",
    "display_upload_history",
    "get_quality_issues",
    "get_repair_history",
    "display_repair_history",
    "get_dataset_summary",
    "display_dataset_summary",
    "delete_upload",
    "export_upload_to_dict",
]