"""
Change Detection module for Robotics Intelligence Database.

Tracks changes to data points over time, detecting significant
changes and generating change reports.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from .database import Database

logger = logging.getLogger(__name__)


@dataclass
class Change:
    """Represents a detected change in data."""
    data_point_id: int
    sector: str
    dimension: str
    old_value: Any
    new_value: Any
    percent_change: Optional[float]
    change_type: str  # 'increase', 'decrease', 'new', 'updated', 'removed'
    significance: str  # 'high', 'medium', 'low'
    detected_at: str
    period: str  # e.g., '2025-01 vs 2024-12'


class ChangeDetector:
    """Detects and tracks changes in robotics intelligence data."""

    # Thresholds for change significance
    SIGNIFICANCE_THRESHOLDS = {
        "high": 20.0,    # >20% change
        "medium": 10.0,  # 10-20% change
        "low": 5.0       # 5-10% change
    }

    def __init__(self, db: Database = None):
        """
        Initialize change detector.

        Args:
            db: Database instance
        """
        self.db = db or Database()

    def _calculate_percent_change(self, old_value: float,
                                   new_value: float) -> Optional[float]:
        """Calculate percentage change between values."""
        if old_value is None or new_value is None:
            return None
        if old_value == 0:
            return None if new_value == 0 else 100.0
        return ((new_value - old_value) / abs(old_value)) * 100

    def _determine_significance(self, percent_change: Optional[float]) -> str:
        """Determine significance level of a change."""
        if percent_change is None:
            return "low"
        abs_change = abs(percent_change)
        if abs_change >= self.SIGNIFICANCE_THRESHOLDS["high"]:
            return "high"
        elif abs_change >= self.SIGNIFICANCE_THRESHOLDS["medium"]:
            return "medium"
        elif abs_change >= self.SIGNIFICANCE_THRESHOLDS["low"]:
            return "low"
        return "minimal"

    def compare_periods(self, sector: str, dimension: str,
                        period1_year: int, period1_month: int,
                        period2_year: int, period2_month: int) -> Optional[Change]:
        """
        Compare data points between two periods.

        Args:
            sector: Sector name
            dimension: Dimension name
            period1_year: First period year
            period1_month: First period month
            period2_year: Second period year
            period2_month: Second period month

        Returns:
            Change object if significant change detected, None otherwise
        """
        # Get data points for both periods
        data1 = self.db.get_data_points(
            sector_name=sector,
            dimension_name=dimension,
            year=period1_year,
            limit=10
        )
        data1 = [d for d in data1 if d.get("month") == period1_month or d.get("month") is None]

        data2 = self.db.get_data_points(
            sector_name=sector,
            dimension_name=dimension,
            year=period2_year,
            limit=10
        )
        data2 = [d for d in data2 if d.get("month") == period2_month or d.get("month") is None]

        if not data1 and not data2:
            return None

        # Get most recent/reliable values from each period
        old_value = data1[0].get("value") if data1 else None
        new_value = data2[0].get("value") if data2 else None

        # Determine change type
        if old_value is None and new_value is not None:
            change_type = "new"
        elif old_value is not None and new_value is None:
            change_type = "removed"
        elif old_value is not None and new_value is not None:
            if new_value > old_value:
                change_type = "increase"
            elif new_value < old_value:
                change_type = "decrease"
            else:
                return None  # No change
        else:
            return None

        percent_change = self._calculate_percent_change(old_value, new_value)
        significance = self._determine_significance(percent_change)

        if significance == "minimal":
            return None

        return Change(
            data_point_id=data2[0]["id"] if data2 else data1[0]["id"],
            sector=sector,
            dimension=dimension,
            old_value=old_value,
            new_value=new_value,
            percent_change=percent_change,
            change_type=change_type,
            significance=significance,
            detected_at=datetime.now().isoformat(),
            period=f"{period2_year}-{period2_month:02d} vs {period1_year}-{period1_month:02d}"
        )

    def detect_month_over_month_changes(self, year: int = None,
                                         month: int = None) -> List[Change]:
        """
        Detect all month-over-month changes.

        Args:
            year: Current year (defaults to now)
            month: Current month (defaults to now)

        Returns:
            list: List of Change objects
        """
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        # Calculate previous month
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        changes = []
        sectors = self.db.get_sectors()
        dimensions = self.db.get_dimensions()

        for sector in sectors:
            for dim in dimensions:
                change = self.compare_periods(
                    sector["name"], dim["name"],
                    prev_year, prev_month,
                    year, month
                )
                if change:
                    changes.append(change)

        # Sort by significance
        significance_order = {"high": 0, "medium": 1, "low": 2}
        changes.sort(key=lambda c: significance_order.get(c.significance, 3))

        logger.info(f"Detected {len(changes)} month-over-month changes")
        return changes

    def detect_year_over_year_changes(self, year: int = None) -> List[Change]:
        """
        Detect year-over-year changes for annual data.

        Args:
            year: Current year

        Returns:
            list: List of Change objects
        """
        year = year or datetime.now().year
        prev_year = year - 1

        changes = []
        sectors = self.db.get_sectors()
        dimensions = self.db.get_dimensions()

        for sector in sectors:
            for dim in dimensions:
                # Get annual data (month=None)
                data_current = self.db.get_data_points(
                    sector_name=sector["name"],
                    dimension_name=dim["name"],
                    year=year,
                    limit=5
                )
                data_current = [d for d in data_current if d.get("month") is None]

                data_prev = self.db.get_data_points(
                    sector_name=sector["name"],
                    dimension_name=dim["name"],
                    year=prev_year,
                    limit=5
                )
                data_prev = [d for d in data_prev if d.get("month") is None]

                if not data_current and not data_prev:
                    continue

                old_value = data_prev[0].get("value") if data_prev else None
                new_value = data_current[0].get("value") if data_current else None

                if old_value is None and new_value is None:
                    continue

                if old_value == new_value:
                    continue

                if old_value is None:
                    change_type = "new"
                elif new_value is None:
                    change_type = "removed"
                elif new_value > old_value:
                    change_type = "increase"
                else:
                    change_type = "decrease"

                percent_change = self._calculate_percent_change(old_value, new_value)
                significance = self._determine_significance(percent_change)

                if significance != "minimal":
                    changes.append(Change(
                        data_point_id=data_current[0]["id"] if data_current else data_prev[0]["id"],
                        sector=sector["name"],
                        dimension=dim["name"],
                        old_value=old_value,
                        new_value=new_value,
                        percent_change=percent_change,
                        change_type=change_type,
                        significance=significance,
                        detected_at=datetime.now().isoformat(),
                        period=f"{year} vs {prev_year}"
                    ))

        return changes

    def get_change_history(self, sector: str = None,
                           since_days: int = 30) -> List[Dict[str, Any]]:
        """
        Get change history from the changes_log table.

        Args:
            sector: Optional sector filter
            since_days: How many days back to look

        Returns:
            list: Change log entries
        """
        since = datetime.now() - timedelta(days=since_days)
        changes = self.db.get_changes(
            table_name="data_points",
            since=since,
            limit=200
        )

        if sector:
            # Filter by sector (would need to join, simplified here)
            pass

        return changes


class ChangeReporter:
    """Generates reports from detected changes."""

    def __init__(self, detector: ChangeDetector = None):
        """
        Initialize reporter.

        Args:
            detector: ChangeDetector instance
        """
        self.detector = detector or ChangeDetector()

    def generate_monthly_report(self, year: int = None,
                                 month: int = None) -> Dict[str, Any]:
        """
        Generate a monthly change report.

        Args:
            year: Report year
            month: Report month

        Returns:
            dict: Structured report
        """
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        changes = self.detector.detect_month_over_month_changes(year, month)

        # Group by significance
        by_significance = {"high": [], "medium": [], "low": []}
        for change in changes:
            if change.significance in by_significance:
                by_significance[change.significance].append(change)

        # Group by sector
        by_sector = {}
        for change in changes:
            if change.sector not in by_sector:
                by_sector[change.sector] = []
            by_sector[change.sector].append(change)

        return {
            "report_type": "monthly_changes",
            "period": f"{year}-{month:02d}",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_changes": len(changes),
                "high_significance": len(by_significance["high"]),
                "medium_significance": len(by_significance["medium"]),
                "low_significance": len(by_significance["low"])
            },
            "changes_by_significance": {
                sig: [self._change_to_dict(c) for c in changes_list]
                for sig, changes_list in by_significance.items()
            },
            "changes_by_sector": {
                sector: [self._change_to_dict(c) for c in changes_list]
                for sector, changes_list in by_sector.items()
            }
        }

    def generate_annual_report(self, year: int = None) -> Dict[str, Any]:
        """
        Generate annual change report.

        Args:
            year: Report year

        Returns:
            dict: Structured report
        """
        year = year or datetime.now().year
        changes = self.detector.detect_year_over_year_changes(year)

        return {
            "report_type": "annual_changes",
            "year": year,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_changes": len(changes),
                "increases": len([c for c in changes if c.change_type == "increase"]),
                "decreases": len([c for c in changes if c.change_type == "decrease"]),
                "new_data": len([c for c in changes if c.change_type == "new"])
            },
            "changes": [self._change_to_dict(c) for c in changes]
        }

    def _change_to_dict(self, change: Change) -> Dict[str, Any]:
        """Convert Change dataclass to dictionary."""
        return {
            "data_point_id": change.data_point_id,
            "sector": change.sector,
            "dimension": change.dimension,
            "old_value": change.old_value,
            "new_value": change.new_value,
            "percent_change": round(change.percent_change, 2) if change.percent_change else None,
            "change_type": change.change_type,
            "significance": change.significance,
            "period": change.period
        }

    def format_changes_as_text(self, changes: List[Change]) -> str:
        """
        Format changes as human-readable text.

        Args:
            changes: List of Change objects

        Returns:
            str: Formatted text
        """
        if not changes:
            return "No significant changes detected."

        lines = ["SIGNIFICANT CHANGES DETECTED", "=" * 40, ""]

        for change in changes:
            direction = "+" if change.change_type == "increase" else "-"
            percent_str = f" ({direction}{abs(change.percent_change):.1f}%)" if change.percent_change else ""

            lines.append(f"[{change.significance.upper()}] {change.sector} - {change.dimension}")
            lines.append(f"  {change.old_value} -> {change.new_value}{percent_str}")
            lines.append(f"  Period: {change.period}")
            lines.append("")

        return "\n".join(lines)


def get_monthly_changes(year: int = None, month: int = None) -> Dict[str, Any]:
    """
    Convenience function to get monthly change report.

    Args:
        year: Report year
        month: Report month

    Returns:
        dict: Change report
    """
    reporter = ChangeReporter()
    return reporter.generate_monthly_report(year, month)


if __name__ == "__main__":
    # Test change detection
    logging.basicConfig(level=logging.INFO)

    db = Database()
    detector = ChangeDetector(db)

    # Get database stats
    stats = db.get_statistics()
    print(f"Database has {stats['data_points_count']} data points")

    # Run change detection
    reporter = ChangeReporter(detector)
    report = reporter.generate_monthly_report()
    print(json.dumps(report, indent=2))
