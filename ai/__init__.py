"""DataFix AI Intelligence Layer.

This package provides machine learning anomaly detection and autonomous
remediation recommendation capabilities for the DataFix Engine.
"""

from ai.anomaly_detector import detect_anomalies
from ai.recommender import (
    generate_recommendations,
    apply_recommendation,
    apply_all_safe_recommendations,
    RemediationRecommendation,
    DestructiveOperationBlockedError,
)

__all__ = [
    "detect_anomalies",
    "generate_recommendations",
    "apply_recommendation",
    "apply_all_safe_recommendations",
    "RemediationRecommendation",
    "DestructiveOperationBlockedError",
]
