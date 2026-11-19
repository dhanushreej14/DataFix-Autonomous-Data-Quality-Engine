
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
# Database package for DataFix
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
