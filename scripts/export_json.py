#!/usr/bin/env python3
"""
Export JSON Script for Robotics Intelligence Database.

Command-line tool to export database contents and generate
reports in JSON format.

Usage:
    python export_json.py full                    # Export entire database
    python export_json.py sector "Industrial Robotics"
    python export_json.py dimension "market_size"
    python export_json.py validation             # Validation status report
    python export_json.py changes                # Monthly changes report
    python export_json.py interviews             # Interview data
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.reporting import ReportGenerator, JSONExporter, generate_report
from src.config import EXPORTS_DIR


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def export_full_database(output: str = None, pretty: bool = True):
    """Export entire database."""
    print("Exporting full database...")

    generator = ReportGenerator()
    report = generator.generate_full_database_export()

    if output:
        output_path = Path(output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(EXPORTS_DIR) / f"full_export_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    print(f"Statistics:")
    print(f"  Sectors: {report['statistics'].get('sectors_count', 0)}")
    print(f"  Data points: {report['statistics'].get('data_points_count', 0)}")
    print(f"  Interviews: {report['statistics'].get('interviews_count', 0)}")

    return str(output_path)


def export_sector(sector_name: str, output: str = None, pretty: bool = True):
    """Export sector report."""
    print(f"Exporting sector: {sector_name}")

    generator = ReportGenerator()
    report = generator.generate_sector_report(sector_name)

    if "error" in report:
        print(f"ERROR: {report['error']}")
        return None

    if output:
        output_path = Path(output)
    else:
        safe_name = sector_name.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = Path(EXPORTS_DIR) / f"sector_{safe_name}_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    print(f"Data points: {report.get('data_points_count', 0)}")
    print(f"Dimensions covered: {len(report.get('dimensions', {}))}")

    return str(output_path)


def export_dimension(dimension_name: str, year: int = None,
                     output: str = None, pretty: bool = True):
    """Export dimension report."""
    print(f"Exporting dimension: {dimension_name}")
    if year:
        print(f"Year filter: {year}")

    generator = ReportGenerator()
    report = generator.generate_dimension_report(dimension_name, year)

    if "error" in report:
        print(f"ERROR: {report['error']}")
        return None

    if output:
        output_path = Path(output)
    else:
        safe_name = dimension_name.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = Path(EXPORTS_DIR) / f"dimension_{safe_name}_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    print(f"Data points: {report.get('data_points_count', 0)}")
    print(f"Sectors covered: {len(report.get('by_sector', {}))}")

    return str(output_path)


def export_validation_report(output: str = None, pretty: bool = True):
    """Export validation status report."""
    print("Exporting validation report...")

    generator = ReportGenerator()
    report = generator.generate_validation_report()

    if output:
        output_path = Path(output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = Path(EXPORTS_DIR) / f"validation_report_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    stats = report.get("statistics", {})
    print(f"Total data points: {stats.get('total_data_points', 0)}")
    print(f"Pending: {stats.get('pending_count', 0)}")
    print(f"Validated: {stats.get('validated_count', 0)}")

    return str(output_path)


def export_changes_report(year: int = None, month: int = None,
                          output: str = None, pretty: bool = True):
    """Export changes report."""
    print("Exporting changes report...")

    generator = ReportGenerator()
    report = generator.generate_changes_report(year, month)

    if output:
        output_path = Path(output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = Path(EXPORTS_DIR) / f"changes_report_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    summary = report.get("summary", {})
    print(f"Total changes: {summary.get('total_changes', 0)}")
    print(f"High significance: {summary.get('high_significance', 0)}")

    return str(output_path)


def export_interviews(output: str = None, pretty: bool = True):
    """Export interview report."""
    print("Exporting interview report...")

    generator = ReportGenerator()
    report = generator.generate_interview_report()

    if output:
        output_path = Path(output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = Path(EXPORTS_DIR) / f"interviews_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    print(f"Total interviews: {report.get('total_interviews', 0)}")

    return str(output_path)


def export_time_series(sector: str, dimension: str,
                       output: str = None, pretty: bool = True):
    """Export time series data."""
    print(f"Exporting time series: {sector} / {dimension}")

    generator = ReportGenerator()
    report = generator.generate_time_series_report(sector, dimension)

    if output:
        output_path = Path(output)
    else:
        safe_sector = sector.lower().replace(" ", "_")
        safe_dim = dimension.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = Path(EXPORTS_DIR) / f"timeseries_{safe_sector}_{safe_dim}_{timestamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(report, f, indent=2, default=str)
        else:
            json.dump(report, f, default=str)

    print(f"Exported to: {output_path}")
    print(f"Data points: {report.get('data_points_count', 0)}")

    return str(output_path)


def list_available_data():
    """List what data is available for export."""
    print("Available data for export:")
    print()

    db = Database()
    stats = db.get_statistics()

    print("SECTORS:")
    for sector in db.get_sectors():
        count = stats.get("data_points_by_sector", {}).get(sector["name"], 0)
        print(f"  - {sector['name']} ({count} data points)")

    print()
    print("DIMENSIONS:")
    for dim in db.get_dimensions():
        print(f"  - {dim['name']} ({dim.get('unit', 'N/A')})")

    print()
    print("STATISTICS:")
    print(f"  Total data points: {stats.get('data_points_count', 0)}")
    print(f"  Total sources: {stats.get('sources_count', 0)}")
    print(f"  Total interviews: {stats.get('interviews_count', 0)}")

    print()
    print("VALIDATION STATUS:")
    breakdown = stats.get("validation_breakdown", {})
    for status, count in breakdown.items():
        print(f"  {status}: {count}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Robotics Intelligence Database Export Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_json.py list                     # List available data
  python export_json.py full                     # Export entire database
  python export_json.py sector "Industrial Robotics"
  python export_json.py dimension market_size --year 2025
  python export_json.py validation
  python export_json.py changes --year 2025 --month 1
  python export_json.py interviews
  python export_json.py timeseries "Mobile Robotics" market_size
        """
    )

    parser.add_argument(
        "command",
        choices=["list", "full", "sector", "dimension", "validation",
                 "changes", "interviews", "timeseries"],
        help="Export command"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target to export (sector name, dimension name, etc.)"
    )
    parser.add_argument(
        "target2",
        nargs="?",
        help="Second target (for timeseries: dimension name)"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=None,
        help="Year filter"
    )
    parser.add_argument(
        "--month", "-m",
        type=int,
        default=None,
        help="Month filter"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no pretty printing)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    pretty = not args.compact

    if args.command == "list":
        list_available_data()

    elif args.command == "full":
        export_full_database(args.output, pretty)

    elif args.command == "sector":
        if not args.target:
            print("ERROR: Sector name required")
            sys.exit(1)
        export_sector(args.target, args.output, pretty)

    elif args.command == "dimension":
        if not args.target:
            print("ERROR: Dimension name required")
            sys.exit(1)
        export_dimension(args.target, args.year, args.output, pretty)

    elif args.command == "validation":
        export_validation_report(args.output, pretty)

    elif args.command == "changes":
        export_changes_report(args.year, args.month, args.output, pretty)

    elif args.command == "interviews":
        export_interviews(args.output, pretty)

    elif args.command == "timeseries":
        if not args.target or not args.target2:
            print("ERROR: Both sector and dimension names required")
            print("Usage: export_json.py timeseries <sector> <dimension>")
            sys.exit(1)
        export_time_series(args.target, args.target2, args.output, pretty)


if __name__ == "__main__":
    main()
