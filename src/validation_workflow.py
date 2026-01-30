"""
Validation Workflow module for Robotics Intelligence Database.

Manages the workflow for reviewing and validating data points,
with support for batch operations and validation rules.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .database import Database
from .config import VALIDATION_STATES, CONFIDENCE_LEVELS

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Validation status enum."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    VALIDATED = "validated"
    REJECTED = "rejected"
    OUTDATED = "outdated"


@dataclass
class ValidationRule:
    """Represents a validation rule."""
    name: str
    description: str
    check_fn: Callable[[Dict[str, Any]], bool]
    severity: str = "warning"  # 'error', 'warning', 'info'
    auto_reject: bool = False


@dataclass
class ValidationResult:
    """Result of a validation check."""
    data_point_id: int
    passed: bool
    rules_checked: int
    rules_passed: int
    rules_failed: int
    failures: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    recommendation: str = ""


class ValidationRules:
    """Collection of validation rules for data points."""

    @staticmethod
    def has_source(dp: Dict[str, Any]) -> bool:
        """Check if data point has a source."""
        return dp.get("source_id") is not None or dp.get("source_url") is not None

    @staticmethod
    def has_year(dp: Dict[str, Any]) -> bool:
        """Check if data point has a year."""
        return dp.get("year") is not None

    @staticmethod
    def value_not_null(dp: Dict[str, Any]) -> bool:
        """Check if data point has a value."""
        return (dp.get("value") is not None or
                dp.get("value_text") is not None or
                dp.get("value_json") is not None)

    @staticmethod
    def reasonable_market_size(dp: Dict[str, Any]) -> bool:
        """Check if market size is within reasonable bounds."""
        if dp.get("dimension_name") != "market_size":
            return True
        value = dp.get("value")
        if value is None:
            return True
        # Market size should be between 0 and 1 trillion
        return 0 <= value <= 1000

    @staticmethod
    def reasonable_growth_rate(dp: Dict[str, Any]) -> bool:
        """Check if growth rate is within reasonable bounds."""
        if dp.get("dimension_name") != "market_growth_rate":
            return True
        value = dp.get("value")
        if value is None:
            return True
        # Growth rate should be between -100% and 500%
        return -100 <= value <= 500

    @staticmethod
    def recent_year(dp: Dict[str, Any]) -> bool:
        """Check if year is not too old."""
        year = dp.get("year")
        if year is None:
            return True
        current_year = datetime.now().year
        return year >= current_year - 5

    @staticmethod
    def valid_confidence(dp: Dict[str, Any]) -> bool:
        """Check if confidence level is valid."""
        confidence = dp.get("confidence")
        return confidence in CONFIDENCE_LEVELS


# Default validation rules
DEFAULT_RULES = [
    ValidationRule(
        name="has_source",
        description="Data point must have a source",
        check_fn=ValidationRules.has_source,
        severity="warning"
    ),
    ValidationRule(
        name="has_year",
        description="Data point must have a year",
        check_fn=ValidationRules.has_year,
        severity="warning"
    ),
    ValidationRule(
        name="value_not_null",
        description="Data point must have a value",
        check_fn=ValidationRules.value_not_null,
        severity="error",
        auto_reject=True
    ),
    ValidationRule(
        name="reasonable_market_size",
        description="Market size must be reasonable (0-1000B)",
        check_fn=ValidationRules.reasonable_market_size,
        severity="error"
    ),
    ValidationRule(
        name="reasonable_growth_rate",
        description="Growth rate must be reasonable (-100% to 500%)",
        check_fn=ValidationRules.reasonable_growth_rate,
        severity="error"
    ),
    ValidationRule(
        name="recent_year",
        description="Data should be from last 5 years",
        check_fn=ValidationRules.recent_year,
        severity="info"
    ),
    ValidationRule(
        name="valid_confidence",
        description="Confidence level must be valid",
        check_fn=ValidationRules.valid_confidence,
        severity="warning"
    )
]


class ValidationWorkflow:
    """
    Manages the data validation workflow.
    """

    def __init__(self, db: Database = None, rules: List[ValidationRule] = None):
        """
        Initialize validation workflow.

        Args:
            db: Database instance
            rules: Custom validation rules (uses defaults if not provided)
        """
        self.db = db or Database()
        self.rules = rules or DEFAULT_RULES

    def validate_data_point(self, data_point_id: int) -> ValidationResult:
        """
        Validate a single data point against all rules.

        Args:
            data_point_id: ID of data point to validate

        Returns:
            ValidationResult with check results
        """
        # Get data point with full details
        data_points = self.db.get_data_points(limit=1000)
        dp = next((d for d in data_points if d["id"] == data_point_id), None)

        if not dp:
            return ValidationResult(
                data_point_id=data_point_id,
                passed=False,
                rules_checked=0,
                rules_passed=0,
                rules_failed=1,
                failures=[{"rule": "exists", "message": "Data point not found"}],
                recommendation="reject"
            )

        failures = []
        warnings = []
        passed_count = 0
        should_auto_reject = False

        for rule in self.rules:
            try:
                result = rule.check_fn(dp)
                if result:
                    passed_count += 1
                else:
                    msg = {"rule": rule.name, "message": rule.description}
                    if rule.severity == "error":
                        failures.append(msg)
                        if rule.auto_reject:
                            should_auto_reject = True
                    else:
                        warnings.append(msg)
            except Exception as e:
                logger.warning(f"Rule {rule.name} failed with error: {e}")
                warnings.append({"rule": rule.name, "message": f"Check error: {e}"})

        # Determine recommendation
        if should_auto_reject or len(failures) >= 2:
            recommendation = "reject"
        elif failures:
            recommendation = "review"
        elif warnings:
            recommendation = "review"
        else:
            recommendation = "validate"

        return ValidationResult(
            data_point_id=data_point_id,
            passed=len(failures) == 0,
            rules_checked=len(self.rules),
            rules_passed=passed_count,
            rules_failed=len(failures),
            failures=failures,
            warnings=warnings,
            recommendation=recommendation
        )

    def get_pending_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get data points pending validation.

        Args:
            limit: Maximum items to return

        Returns:
            list: Pending data points with validation checks
        """
        pending = self.db.get_data_points(
            validation_status="pending",
            limit=limit
        )

        # Add validation check results
        for dp in pending:
            result = self.validate_data_point(dp["id"])
            dp["validation_check"] = {
                "passed": result.passed,
                "failures": result.failures,
                "warnings": result.warnings,
                "recommendation": result.recommendation
            }

        return pending

    def get_review_queue(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get items currently in review.

        Args:
            limit: Maximum items to return

        Returns:
            list: Data points in review
        """
        return self.db.get_data_points(
            validation_status="in_review",
            limit=limit
        )

    def start_review(self, data_point_id: int, reviewer: str) -> bool:
        """
        Move a data point to in_review status.

        Args:
            data_point_id: Data point ID
            reviewer: Name of reviewer

        Returns:
            bool: Success
        """
        return self.db.update_data_point_validation(
            data_point_id,
            status="in_review",
            validated_by=reviewer,
            notes=f"Review started by {reviewer}"
        )

    def validate_item(self, data_point_id: int, validator: str,
                      notes: str = None) -> bool:
        """
        Mark a data point as validated.

        Args:
            data_point_id: Data point ID
            validator: Name of validator
            notes: Optional notes

        Returns:
            bool: Success
        """
        # Run validation checks first
        result = self.validate_data_point(data_point_id)

        if result.recommendation == "reject":
            logger.warning(f"Attempting to validate item {data_point_id} "
                          f"but recommendation is reject")

        return self.db.update_data_point_validation(
            data_point_id,
            status="validated",
            validated_by=validator,
            notes=notes
        )

    def reject_item(self, data_point_id: int, validator: str,
                    reason: str) -> bool:
        """
        Reject a data point.

        Args:
            data_point_id: Data point ID
            validator: Name of validator
            reason: Rejection reason

        Returns:
            bool: Success
        """
        return self.db.update_data_point_validation(
            data_point_id,
            status="rejected",
            validated_by=validator,
            notes=f"Rejected: {reason}"
        )

    def mark_outdated(self, data_point_id: int, reason: str = None) -> bool:
        """
        Mark a data point as outdated.

        Args:
            data_point_id: Data point ID
            reason: Optional reason

        Returns:
            bool: Success
        """
        return self.db.update_data_point_validation(
            data_point_id,
            status="outdated",
            validated_by="system",
            notes=reason or "Marked outdated by system"
        )

    def batch_validate(self, data_point_ids: List[int],
                       validator: str) -> Dict[str, int]:
        """
        Batch validate multiple data points.

        Args:
            data_point_ids: List of data point IDs
            validator: Name of validator

        Returns:
            dict: Counts of validated and failed items
        """
        validated = 0
        failed = 0

        for dp_id in data_point_ids:
            result = self.validate_data_point(dp_id)
            if result.recommendation != "reject":
                if self.validate_item(dp_id, validator):
                    validated += 1
                else:
                    failed += 1
            else:
                failed += 1

        return {"validated": validated, "failed": failed}

    def auto_validate_high_confidence(self, validator: str = "auto") -> Dict[str, int]:
        """
        Automatically validate items with high confidence from reliable sources.

        Args:
            validator: Validator name

        Returns:
            dict: Counts of processed items
        """
        pending = self.db.get_data_points(
            validation_status="pending",
            limit=100
        )

        auto_validated = 0
        flagged_for_review = 0

        for dp in pending:
            # Auto-validate if high confidence
            if dp.get("confidence") == "high":
                result = self.validate_data_point(dp["id"])
                if result.passed:
                    self.validate_item(dp["id"], validator,
                                      "Auto-validated: high confidence, passed all checks")
                    auto_validated += 1
                else:
                    self.start_review(dp["id"], "auto")
                    flagged_for_review += 1
            else:
                # Medium/low confidence needs manual review
                flagged_for_review += 1

        return {
            "auto_validated": auto_validated,
            "flagged_for_review": flagged_for_review
        }

    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation workflow statistics.

        Returns:
            dict: Validation statistics
        """
        stats = self.db.get_statistics()

        return {
            "total_data_points": stats.get("data_points_count", 0),
            "by_status": stats.get("validation_breakdown", {}),
            "pending_count": stats.get("validation_breakdown", {}).get("pending", 0),
            "validated_count": stats.get("validation_breakdown", {}).get("validated", 0),
            "rejected_count": stats.get("validation_breakdown", {}).get("rejected", 0)
        }


def validation_result_to_dict(result: ValidationResult) -> Dict[str, Any]:
    """Convert ValidationResult to dictionary."""
    return {
        "data_point_id": result.data_point_id,
        "passed": result.passed,
        "rules_checked": result.rules_checked,
        "rules_passed": result.rules_passed,
        "rules_failed": result.rules_failed,
        "failures": result.failures,
        "warnings": result.warnings,
        "recommendation": result.recommendation
    }


if __name__ == "__main__":
    # Test validation workflow
    logging.basicConfig(level=logging.INFO)

    db = Database()
    workflow = ValidationWorkflow(db)

    # Get stats
    stats = workflow.get_validation_stats()
    print(f"Validation stats: {json.dumps(stats, indent=2)}")

    # Get pending items
    pending = workflow.get_pending_items(limit=5)
    print(f"\nPending items: {len(pending)}")
    for item in pending:
        print(f"  - ID {item['id']}: {item.get('dimension_name')} = {item.get('value')}")
        print(f"    Recommendation: {item['validation_check']['recommendation']}")
