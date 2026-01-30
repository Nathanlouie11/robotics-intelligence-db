"""
Tests for database module.
"""

import os
import tempfile
import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db = Database(path)
    db.seed_default_data()
    yield db
    os.unlink(path)


class TestDatabase:
    """Test database operations."""

    def test_initialization(self, temp_db):
        """Test database initialization."""
        stats = temp_db.get_statistics()
        assert stats['sectors_count'] > 0
        assert stats['dimensions_count'] > 0

    def test_get_sectors(self, temp_db):
        """Test getting sectors."""
        sectors = temp_db.get_sectors()
        assert len(sectors) > 0
        assert 'name' in sectors[0]
        assert 'subcategories' in sectors[0]

    def test_get_sector_by_name(self, temp_db):
        """Test getting sector by name."""
        sector = temp_db.get_sector_by_name("Industrial Robotics")
        assert sector is not None
        assert sector['name'] == "Industrial Robotics"

    def test_get_dimensions(self, temp_db):
        """Test getting dimensions."""
        dimensions = temp_db.get_dimensions()
        assert len(dimensions) > 0
        assert 'name' in dimensions[0]

    def test_get_dimension_by_name(self, temp_db):
        """Test getting dimension by name."""
        dim = temp_db.get_dimension_by_name("market_size")
        assert dim is not None
        assert dim['name'] == "market_size"

    def test_add_source(self, temp_db):
        """Test adding a source."""
        source_id = temp_db.add_source(
            name="Test Source",
            url="https://example.com",
            source_type="research_report"
        )
        assert source_id > 0

    def test_add_data_point(self, temp_db):
        """Test adding a data point."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=50.5,
            sector_name="Industrial Robotics",
            year=2025,
            confidence="high",
            notes="Test data point"
        )
        assert dp_id > 0

    def test_get_data_points(self, temp_db):
        """Test getting data points."""
        # Add a data point first
        temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            sector_name="Industrial Robotics",
            year=2025
        )

        data_points = temp_db.get_data_points(
            sector_name="Industrial Robotics",
            dimension_name="market_size"
        )
        assert len(data_points) > 0

    def test_update_validation_status(self, temp_db):
        """Test updating validation status."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=75.0,
            year=2025
        )

        result = temp_db.update_data_point_validation(
            dp_id,
            status="validated",
            validated_by="test_user"
        )
        assert result is True

        # Verify update
        data_points = temp_db.get_data_points(
            validation_status="validated"
        )
        assert any(dp['id'] == dp_id for dp in data_points)

    def test_add_interview(self, temp_db):
        """Test adding an interview."""
        interview_id = temp_db.add_interview(
            expert_name="John Doe",
            expert_title="CTO",
            expert_company="RoboCorp",
            topics=["automation", "AI"],
            key_insights=["Market growing fast"]
        )
        assert interview_id > 0

    def test_get_interviews(self, temp_db):
        """Test getting interviews."""
        temp_db.add_interview(
            expert_name="Jane Smith",
            expert_company="TechBot"
        )

        interviews = temp_db.get_interviews()
        assert len(interviews) > 0

    def test_research_session_tracking(self, temp_db):
        """Test research session tracking."""
        session_id = temp_db.start_research_session(
            session_type="sector_deep_dive",
            target="Test Sector"
        )
        assert session_id > 0

        temp_db.update_research_session(
            session_id,
            queries_run=10,
            sources_found=50,
            status="completed"
        )

    def test_get_changes(self, temp_db):
        """Test getting change history."""
        # Add and update a data point to create changes
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=100.0,
            year=2025
        )

        temp_db.update_data_point_validation(
            dp_id,
            status="validated",
            validated_by="test"
        )

        changes = temp_db.get_changes(limit=10)
        assert len(changes) > 0

    def test_get_statistics(self, temp_db):
        """Test getting statistics."""
        stats = temp_db.get_statistics()

        assert 'sectors_count' in stats
        assert 'dimensions_count' in stats
        assert 'data_points_count' in stats
        assert 'validation_breakdown' in stats


class TestDataPointValues:
    """Test different data point value types."""

    def test_numeric_value(self, temp_db):
        """Test numeric value storage."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=123.45,
            year=2025
        )

        data_points = temp_db.get_data_points(limit=100)
        dp = next(d for d in data_points if d['id'] == dp_id)
        assert dp['value'] == 123.45

    def test_text_value(self, temp_db):
        """Test text value storage."""
        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value="Growing rapidly",
            year=2025
        )

        data_points = temp_db.get_data_points(limit=100)
        dp = next(d for d in data_points if d['id'] == dp_id)
        assert dp['value_text'] == "Growing rapidly"

    def test_json_value(self, temp_db):
        """Test JSON value storage."""
        complex_value = {
            "regions": {"NA": 40, "EU": 30, "APAC": 30},
            "trend": "increasing"
        }

        dp_id = temp_db.add_data_point(
            dimension_name="market_size",
            value=complex_value,
            year=2025
        )

        data_points = temp_db.get_data_points(limit=100)
        dp = next(d for d in data_points if d['id'] == dp_id)
        assert dp['value_structured'] == complex_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
