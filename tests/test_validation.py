"""
Tests for validation workflow module.
"""

import os
import tempfile
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.validation_workflow import (
    ValidationWorkflow,
    ValidationRules,
    ValidationResult,
    validation_result_to_dict
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = Database(path)
    db.seed_default_data()
    yield db
    os.unlink(path)


@pytest.fixture
def workflow(temp_db):
    """Create validation workflow with temp database."""
    return ValidationWorkflow(temp_db)


class TestValidationRules:
    """Test individual validation rules."""

    def test_has_source_pass(self):
        """Test has_source rule passes."""
        dp = {"source_id": 1}
        assert ValidationRules.has_source(dp) is True

    def test_has_source_fail(self):
        """Test has_source rule fails."""
        dp = {"source_id": None, "source_url": None}
        assert ValidationRules.has_source(dp) is False

    def test_has_year_pass(self):
        """Test has_year rule passes."""
        dp = {"year": 2025}
        assert ValidationRules.has_year(dp) is True

    def test_has_year_fail(self):
        """Test has_year rule fails."""
        dp = {"year": None}
        assert ValidationRules.has_year(dp) is False

    def test_value_not_null_numeric(self):
        """Test value_not_null with numeric."""
        dp = {"value": 100.5}
        assert ValidationRules.value_not_null(dp) is True

    def test_value_not_null_text(self):
        """Test value_not_null with text."""
        dp = {"value_text": "some text"}
        assert ValidationRules.value_not_null(dp) is True

    def test_value_not_null_fail(self):
        """Test value_not_null fails."""
        dp = {"value": None, "value_text": None, "value_json": None}
        assert ValidationRules.value_not_null(dp) is False

    def test_reasonable_market_size_pass(self):
        """Test reasonable_market_size passes."""
        dp = {"dimension_name": "market_size", "value": 50}
        assert ValidationRules.reasonable_market_size(dp) is True

    def test_reasonable_market_size_fail(self):
        """Test reasonable_market_size fails."""
        dp = {"dimension_name": "market_size", "value": 5000}
        assert ValidationRules.reasonable_market_size(dp) is False

    def test_reasonable_market_size_skip(self):
        """Test reasonable_market_size skips non-market dimensions."""
        dp = {"dimension_name": "adoption_rate", "value": 5000}
        assert ValidationRules.reasonable_market_size(dp) is True

    def test_reasonable_growth_rate_pass(self):
        """Test reasonable_growth_rate passes."""
        dp = {"dimension_name": "market_growth_rate", "value": 25}
        assert ValidationRules.reasonable_growth_rate(dp) is True

    def test_reasonable_growth_rate_fail(self):
        """Test reasonable_growth_rate fails."""
        dp = {"dimension_name": "market_growth_rate", "value": 1000}
        assert ValidationRules.reasonable_growth_rate(dp) is False

    def test_valid_confidence_pass(self):
        """Test valid_confidence passes."""
        dp = {"confidence": "high"}
        assert ValidationRules.valid_confidence(dp) is True

    def test_valid_confidence_fail(self):
        """Test valid_confidence fails."""
        dp = {"confidence": "invalid"}
        assert ValidationRules.valid_confidence(dp) is False


class TestValidationWorkflow:
    """Test validation workflow operations."""

    def test_validate_data_point(self, workflow, temp_db):
        """Test validating a data point."""
        # Add a valid data point
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=50.0,
            year=2025,
            confidence="high"
        )

        result = workflow.validate_data_point(dp_id)
        assert isinstance(result, ValidationResult)
        assert result.data_point_id == dp_id

    def test_validate_data_point_not_found(self, workflow):
        """Test validating non-existent data point."""
        result = workflow.validate_data_point(99999)
        assert result.passed is False
        assert len(result.failures) > 0

    def test_get_pending_items(self, workflow, temp_db):
        """Test getting pending items."""
        # Add some pending data points
        temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2025
        )

        pending = workflow.get_pending_items()
        assert len(pending) > 0
        assert 'validation_check' in pending[0]

    def test_start_review(self, workflow, temp_db):
        """Test starting review."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2025
        )

        result = workflow.start_review(dp_id, "test_reviewer")
        assert result is True

    def test_validate_item(self, workflow, temp_db):
        """Test validating an item."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2025,
            confidence="high"
        )

        result = workflow.validate_item(dp_id, "test_validator")
        assert result is True

    def test_reject_item(self, workflow, temp_db):
        """Test rejecting an item."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2025
        )

        result = workflow.reject_item(dp_id, "test_validator", "Invalid data")
        assert result is True

    def test_mark_outdated(self, workflow, temp_db):
        """Test marking item as outdated."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2020
        )

        result = workflow.mark_outdated(dp_id, "Data from 2020")
        assert result is True

    def test_batch_validate(self, workflow, temp_db):
        """Test batch validation."""
        ids = []
        for i in range(3):
            dp_id = temp_db.add_data_point(
                dimension_name="market_size",
                value=100.0 + i,
                year=2025,
                confidence="high"
            )
            ids.append(dp_id)

        result = workflow.batch_validate(ids, "test_validator")
        assert result['validated'] >= 0
        assert result['validated'] + result['failed'] == len(ids)

    def test_get_validation_stats(self, workflow, temp_db):
        """Test getting validation stats."""
        # Add some data points
        temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2025
        )

        stats = workflow.get_validation_stats()
        assert 'total_data_points' in stats
        assert 'by_status' in stats


class TestValidationResultConversion:
    """Test ValidationResult conversion."""

    def test_to_dict(self):
        """Test converting ValidationResult to dict."""
        result = ValidationResult(
            data_point_id=1,
            passed=True,
            rules_checked=5,
            rules_passed=5,
            rules_failed=0,
            failures=[],
            warnings=[],
            recommendation="validate"
        )

        d = validation_result_to_dict(result)
        assert d['data_point_id'] == 1
        assert d['passed'] is True
        assert d['recommendation'] == "validate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
