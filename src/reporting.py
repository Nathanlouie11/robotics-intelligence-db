"""
Reporting module for Robotics Intelligence Database.

Generates structured JSON reports from the database,
with various views and export formats.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .database import Database
from .config import EXPORTS_DIR
from .change_detection import ChangeReporter
from .validation_workflow import ValidationWorkflow

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates various reports from the robotics intelligence database."""

    def __init__(self, db: Database = None):
        """
        Initialize report generator.

        Args:
            db: Database instance
        """
        self.db = db or Database()

    def generate_sector_report(self, sector_name: str,
                                include_pending: bool = True) -> Dict[str, Any]:
        """
        Generate a comprehensive report for a sector.

        Args:
            sector_name: Name of sector
            include_pending: Include pending (unvalidated) data points

        Returns:
            dict: Structured sector report
        """
        sector = self.db.get_sector_by_name(sector_name)
        if not sector:
            return {"error": f"Sector not found: {sector_name}"}

        # Get all data points for sector
        validation_filter = None if include_pending else "validated"
        data_points = self.db.get_data_points(
            sector_name=sector_name,
            validation_status=validation_filter,
            limit=500
        )

        # Group by dimension
        by_dimension = {}
        for dp in data_points:
            dim = dp.get("dimension_name", "unknown")
            if dim not in by_dimension:
                by_dimension[dim] = []
            by_dimension[dim].append({
                "value": dp.get("value"),
                "value_text": dp.get("value_text"),
                "year": dp.get("year"),
                "quarter": dp.get("quarter"),
                "source": dp.get("source_name"),
                "source_url": dp.get("source_url"),
                "confidence": dp.get("confidence"),
                "notes": dp.get("notes")
            })

        # Get subcategories
        sectors = self.db.get_sectors()
        sector_data = next((s for s in sectors if s["name"] == sector_name), {})
        subcategories = [sc["name"] for sc in sector_data.get("subcategories", [])]

        return {
            "report_type": "sector_intelligence",
            "sector": sector_name,
            "description": sector.get("description"),
            "generated_at": datetime.now().isoformat(),
            "subcategories": subcategories,
            "data_points_count": len(data_points),
            "dimensions": by_dimension,
            "summary": self._generate_sector_summary(sector_name, by_dimension)
        }

    def _generate_sector_summary(self, sector_name: str,
                                  by_dimension: Dict) -> Dict[str, Any]:
        """Generate summary statistics for a sector."""
        summary = {
            "sector": sector_name,
            "dimensions_covered": list(by_dimension.keys()),
            "total_data_points": sum(len(v) for v in by_dimension.values())
        }

        # Extract key metrics if available
        if "market_size" in by_dimension and by_dimension["market_size"]:
            latest = max(by_dimension["market_size"],
                        key=lambda x: x.get("year") or 0)
            summary["latest_market_size"] = {
                "value_usd_billions": latest.get("value"),
                "year": latest.get("year"),
                "source": latest.get("source")
            }

        if "market_growth_rate" in by_dimension and by_dimension["market_growth_rate"]:
            latest = max(by_dimension["market_growth_rate"],
                        key=lambda x: x.get("year") or 0)
            summary["latest_growth_rate"] = {
                "value_percent": latest.get("value"),
                "year": latest.get("year"),
                "source": latest.get("source")
            }

        return summary

    def generate_full_database_export(self) -> Dict[str, Any]:
        """
        Export entire database as structured JSON.

        Returns:
            dict: Full database export
        """
        sectors = self.db.get_sectors()
        dimensions = self.db.get_dimensions()
        stats = self.db.get_statistics()

        # Get all validated data points
        all_data_points = self.db.get_data_points(
            validation_status="validated",
            limit=10000
        )

        # Organize by sector and dimension
        data_by_sector = {}
        for dp in all_data_points:
            sector = dp.get("sector_name") or "unclassified"
            dim = dp.get("dimension_name") or "unknown"

            if sector not in data_by_sector:
                data_by_sector[sector] = {}
            if dim not in data_by_sector[sector]:
                data_by_sector[sector][dim] = []

            data_by_sector[sector][dim].append({
                "id": dp["id"],
                "value": dp.get("value"),
                "value_text": dp.get("value_text"),
                "year": dp.get("year"),
                "quarter": dp.get("quarter"),
                "source_name": dp.get("source_name"),
                "source_url": dp.get("source_url"),
                "confidence": dp.get("confidence"),
                "validated_at": dp.get("validated_at"),
                "notes": dp.get("notes")
            })

        return {
            "export_type": "full_database",
            "generated_at": datetime.now().isoformat(),
            "version": "1.0",
            "statistics": stats,
            "schema": {
                "sectors": [{"name": s["name"], "description": s.get("description"),
                            "subcategories": [sc["name"] for sc in s.get("subcategories", [])]}
                           for s in sectors],
                "dimensions": [{"name": d["name"], "unit": d.get("unit"),
                               "description": d.get("description")}
                              for d in dimensions]
            },
            "data": data_by_sector
        }

    def generate_dimension_report(self, dimension_name: str,
                                   year: int = None) -> Dict[str, Any]:
        """
        Generate a report for a specific dimension across all sectors.

        Args:
            dimension_name: Name of dimension
            year: Optional year filter

        Returns:
            dict: Dimension report
        """
        dimension = self.db.get_dimension_by_name(dimension_name)
        if not dimension:
            return {"error": f"Dimension not found: {dimension_name}"}

        data_points = self.db.get_data_points(
            dimension_name=dimension_name,
            year=year,
            limit=500
        )

        # Group by sector
        by_sector = {}
        for dp in data_points:
            sector = dp.get("sector_name") or "unclassified"
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append({
                "value": dp.get("value"),
                "year": dp.get("year"),
                "quarter": dp.get("quarter"),
                "source": dp.get("source_name"),
                "confidence": dp.get("confidence")
            })

        # Calculate aggregates
        all_values = [dp.get("value") for dp in data_points
                     if dp.get("value") is not None]

        aggregates = {}
        if all_values:
            aggregates = {
                "count": len(all_values),
                "min": min(all_values),
                "max": max(all_values),
                "average": sum(all_values) / len(all_values)
            }

        return {
            "report_type": "dimension_analysis",
            "dimension": dimension_name,
            "unit": dimension.get("unit"),
            "description": dimension.get("description"),
            "year_filter": year,
            "generated_at": datetime.now().isoformat(),
            "data_points_count": len(data_points),
            "by_sector": by_sector,
            "aggregates": aggregates
        }

    def generate_time_series_report(self, sector_name: str,
                                     dimension_name: str) -> Dict[str, Any]:
        """
        Generate time series data for a sector/dimension combination.

        Args:
            sector_name: Sector name
            dimension_name: Dimension name

        Returns:
            dict: Time series report
        """
        data_points = self.db.get_data_points(
            sector_name=sector_name,
            dimension_name=dimension_name,
            limit=200
        )

        # Sort by time
        data_points.sort(key=lambda x: (
            x.get("year") or 0,
            x.get("quarter") or 0,
            x.get("month") or 0
        ))

        time_series = []
        for dp in data_points:
            entry = {
                "year": dp.get("year"),
                "value": dp.get("value")
            }
            if dp.get("quarter"):
                entry["quarter"] = dp["quarter"]
            if dp.get("month"):
                entry["month"] = dp["month"]
            entry["source"] = dp.get("source_name")
            entry["confidence"] = dp.get("confidence")
            time_series.append(entry)

        return {
            "report_type": "time_series",
            "sector": sector_name,
            "dimension": dimension_name,
            "generated_at": datetime.now().isoformat(),
            "data_points_count": len(time_series),
            "time_series": time_series
        }

    def generate_validation_report(self) -> Dict[str, Any]:
        """
        Generate report on validation status.

        Returns:
            dict: Validation status report
        """
        workflow = ValidationWorkflow(self.db)
        stats = workflow.get_validation_stats()

        pending = self.db.get_data_points(validation_status="pending", limit=100)
        in_review = self.db.get_data_points(validation_status="in_review", limit=100)

        return {
            "report_type": "validation_status",
            "generated_at": datetime.now().isoformat(),
            "statistics": stats,
            "pending_items": [
                {
                    "id": dp["id"],
                    "sector": dp.get("sector_name"),
                    "dimension": dp.get("dimension_name"),
                    "value": dp.get("value"),
                    "created_at": dp.get("created_at")
                }
                for dp in pending
            ],
            "in_review_items": [
                {
                    "id": dp["id"],
                    "sector": dp.get("sector_name"),
                    "dimension": dp.get("dimension_name"),
                    "value": dp.get("value"),
                    "validated_by": dp.get("validated_by")
                }
                for dp in in_review
            ]
        }

    def generate_changes_report(self, year: int = None,
                                 month: int = None) -> Dict[str, Any]:
        """
        Generate changes report.

        Args:
            year: Report year
            month: Report month

        Returns:
            dict: Changes report
        """
        reporter = ChangeReporter()
        return reporter.generate_monthly_report(year, month)

    def generate_interview_report(self) -> Dict[str, Any]:
        """
        Generate report on interview data.

        Returns:
            dict: Interview report
        """
        interviews = self.db.get_interviews()

        return {
            "report_type": "interview_intelligence",
            "generated_at": datetime.now().isoformat(),
            "total_interviews": len(interviews),
            "interviews": [
                {
                    "id": i["id"],
                    "expert_name": i.get("expert_name"),
                    "expert_title": i.get("expert_title"),
                    "expert_company": i.get("expert_company"),
                    "interview_date": i.get("interview_date"),
                    "topics": i.get("topics"),
                    "key_insights": i.get("key_insights"),
                    "summary": i.get("summary"),
                    "validation_status": i.get("validation_status")
                }
                for i in interviews
            ]
        }


class JSONExporter:
    """Exports reports to JSON files."""

    def __init__(self, export_dir: str = None):
        """
        Initialize exporter.

        Args:
            export_dir: Directory for exports
        """
        self.export_dir = Path(export_dir or EXPORTS_DIR)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_report(self, report: Dict[str, Any],
                      filename: str = None) -> str:
        """
        Export a report to JSON file.

        Args:
            report: Report dictionary
            filename: Optional filename (auto-generated if not provided)

        Returns:
            str: Path to exported file
        """
        if not filename:
            report_type = report.get("report_type", "report")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type}_{timestamp}.json"

        filepath = self.export_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Exported report to: {filepath}")
        return str(filepath)

    def export_full_database(self, db: Database = None) -> str:
        """
        Export full database to JSON.

        Args:
            db: Database instance

        Returns:
            str: Path to exported file
        """
        generator = ReportGenerator(db)
        report = generator.generate_full_database_export()
        return self.export_report(report, "full_database_export.json")

    def export_sector(self, sector_name: str, db: Database = None) -> str:
        """
        Export sector report to JSON.

        Args:
            sector_name: Sector name
            db: Database instance

        Returns:
            str: Path to exported file
        """
        generator = ReportGenerator(db)
        report = generator.generate_sector_report(sector_name)
        safe_name = sector_name.lower().replace(" ", "_")
        return self.export_report(report, f"sector_{safe_name}.json")


def generate_report(report_type: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to generate reports.

    Args:
        report_type: Type of report
        **kwargs: Additional arguments for report

    Returns:
        dict: Generated report
    """
    generator = ReportGenerator()

    if report_type == "sector":
        return generator.generate_sector_report(kwargs.get("sector_name"))
    elif report_type == "dimension":
        return generator.generate_dimension_report(
            kwargs.get("dimension_name"),
            kwargs.get("year")
        )
    elif report_type == "full":
        return generator.generate_full_database_export()
    elif report_type == "validation":
        return generator.generate_validation_report()
    elif report_type == "changes":
        return generator.generate_changes_report(
            kwargs.get("year"),
            kwargs.get("month")
        )
    elif report_type == "interviews":
        return generator.generate_interview_report()
    else:
        return {"error": f"Unknown report type: {report_type}"}


if __name__ == "__main__":
    # Test report generation
    logging.basicConfig(level=logging.INFO)

    db = Database()
    generator = ReportGenerator(db)

    # Generate and print full export
    report = generator.generate_full_database_export()
    print(json.dumps(report, indent=2, default=str))

    # Export to file
    exporter = JSONExporter()
    filepath = exporter.export_report(report)
    print(f"\nExported to: {filepath}")
