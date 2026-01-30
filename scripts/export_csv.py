#!/usr/bin/env python3
"""
Export CSV Script for Robotics Intelligence Database.

Exports database contents to CSV format for easy import into
Google Sheets, Excel, or other spreadsheet applications.

Usage:
    python export_csv.py                     # Export all data points
    python export_csv.py --sector "Mobile Robotics"
    python export_csv.py --validated-only    # Only validated data
    python export_csv.py --output my_export.csv
"""

import sys
import csv
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.config import EXPORTS_DIR


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def export_data_points_to_csv(
    output_path: str = None,
    sector_filter: str = None,
    dimension_filter: str = None,
    year_filter: int = None,
    validated_only: bool = False
) -> str:
    """
    Export data points to CSV format.

    Args:
        output_path: Output file path
        sector_filter: Filter by sector name
        dimension_filter: Filter by dimension name
        year_filter: Filter by year
        validated_only: Only export validated data points

    Returns:
        str: Path to exported file
    """
    db = Database()

    # Build query parameters
    validation_status = "validated" if validated_only else None

    # Get data points
    data_points = db.get_data_points(
        sector_name=sector_filter,
        dimension_name=dimension_filter,
        year=year_filter,
        validation_status=validation_status,
        limit=10000
    )

    if not data_points:
        print("No data points found matching criteria.")
        return None

    # Define CSV columns (Google Sheets friendly)
    columns = [
        'id',
        'sector',
        'subcategory',
        'dimension',
        'dimension_unit',
        'value_numeric',
        'value_text',
        'year',
        'quarter',
        'month',
        'source_name',
        'source_url',
        'confidence',
        'validation_status',
        'validated_by',
        'validated_at',
        'notes',
        'created_at',
        'updated_at'
    ]

    # Generate output path
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"robotics_data_{timestamp}.csv"
        output_path = Path(EXPORTS_DIR) / filename
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()

        for dp in data_points:
            row = {
                'id': dp.get('id'),
                'sector': dp.get('sector_name', ''),
                'subcategory': dp.get('subcategory_name', ''),
                'dimension': dp.get('dimension_name', ''),
                'dimension_unit': dp.get('dimension_unit', ''),
                'value_numeric': dp.get('value'),
                'value_text': dp.get('value_text') if dp.get('value_text') != 'None' else '',
                'year': dp.get('year'),
                'quarter': dp.get('quarter'),
                'month': dp.get('month'),
                'source_name': dp.get('source_name', ''),
                'source_url': dp.get('source_url', ''),
                'confidence': dp.get('confidence', ''),
                'validation_status': dp.get('validation_status', ''),
                'validated_by': dp.get('validated_by', ''),
                'validated_at': dp.get('validated_at', ''),
                'notes': dp.get('notes', ''),
                'created_at': dp.get('created_at', ''),
                'updated_at': dp.get('updated_at', '')
            }
            writer.writerow(row)

    print(f"Exported {len(data_points)} data points to: {output_path}")
    return str(output_path)


def export_summary_to_csv(output_path: str = None) -> str:
    """
    Export summary statistics by sector and dimension.

    Args:
        output_path: Output file path

    Returns:
        str: Path to exported file
    """
    db = Database()

    # Get all data points
    data_points = db.get_data_points(limit=10000)

    # Aggregate by sector and dimension
    summary = {}
    for dp in data_points:
        sector = dp.get('sector_name', 'Unknown')
        dimension = dp.get('dimension_name', 'Unknown')
        key = (sector, dimension)

        if key not in summary:
            summary[key] = {
                'sector': sector,
                'dimension': dimension,
                'count': 0,
                'min_value': None,
                'max_value': None,
                'avg_value': None,
                'values': [],
                'years': set(),
                'sources': set(),
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0
            }

        summary[key]['count'] += 1

        # Track values for aggregation
        value = dp.get('value')
        if value is not None:
            summary[key]['values'].append(value)

        # Track years
        year = dp.get('year')
        if year:
            summary[key]['years'].add(year)

        # Track sources
        source = dp.get('source_name')
        if source:
            summary[key]['sources'].add(source)

        # Track confidence
        confidence = dp.get('confidence', '')
        if confidence == 'high':
            summary[key]['high_confidence'] += 1
        elif confidence == 'medium':
            summary[key]['medium_confidence'] += 1
        elif confidence == 'low':
            summary[key]['low_confidence'] += 1

    # Calculate aggregates
    for key, data in summary.items():
        values = data['values']
        if values:
            data['min_value'] = min(values)
            data['max_value'] = max(values)
            data['avg_value'] = round(sum(values) / len(values), 2)
        data['year_range'] = f"{min(data['years'])}-{max(data['years'])}" if data['years'] else ''
        data['source_count'] = len(data['sources'])
        del data['values']
        del data['years']
        del data['sources']

    # Generate output path
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"robotics_summary_{timestamp}.csv"
        output_path = Path(EXPORTS_DIR) / filename
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV
    columns = [
        'sector', 'dimension', 'count', 'min_value', 'max_value', 'avg_value',
        'year_range', 'source_count', 'high_confidence', 'medium_confidence', 'low_confidence'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for data in sorted(summary.values(), key=lambda x: (x['sector'], x['dimension'])):
            writer.writerow(data)

    print(f"Exported summary ({len(summary)} rows) to: {output_path}")
    return str(output_path)


def export_growth_rates_to_csv(output_path: str = None) -> str:
    """
    Export just growth rate data in a pivot-friendly format.

    Args:
        output_path: Output file path

    Returns:
        str: Path to exported file
    """
    db = Database()

    # Get growth rate data points
    data_points = db.get_data_points(
        dimension_name="market_growth_rate",
        limit=1000
    )

    # Filter to only those with actual values
    data_points = [dp for dp in data_points if dp.get('value') is not None]

    if not data_points:
        print("No growth rate data found.")
        return None

    # Generate output path
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"growth_rates_{timestamp}.csv"
        output_path = Path(EXPORTS_DIR) / filename
    else:
        output_path = Path(output_path)

    columns = [
        'sector',
        'cagr_percent',
        'forecast_year',
        'source_name',
        'source_url',
        'confidence',
        'notes'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for dp in sorted(data_points, key=lambda x: (x.get('sector_name', ''), -x.get('value', 0))):
            writer.writerow({
                'sector': dp.get('sector_name', ''),
                'cagr_percent': dp.get('value'),
                'forecast_year': dp.get('year'),
                'source_name': dp.get('source_name', ''),
                'source_url': dp.get('source_url', ''),
                'confidence': dp.get('confidence', ''),
                'notes': dp.get('notes', '')
            })

    print(f"Exported {len(data_points)} growth rates to: {output_path}")
    return str(output_path)


def export_market_sizes_to_csv(output_path: str = None) -> str:
    """
    Export market size data with actual values only.

    Args:
        output_path: Output file path

    Returns:
        str: Path to exported file
    """
    db = Database()

    # Get market size data points
    data_points = db.get_data_points(
        dimension_name="market_size",
        limit=1000
    )

    # Filter to only those with actual values
    data_points = [dp for dp in data_points if dp.get('value') is not None]

    if not data_points:
        print("No market size data found.")
        return None

    # Generate output path
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"market_sizes_{timestamp}.csv"
        output_path = Path(EXPORTS_DIR) / filename
    else:
        output_path = Path(output_path)

    columns = [
        'sector',
        'market_size_usd_billions',
        'year',
        'source_name',
        'source_url',
        'confidence',
        'notes'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for dp in sorted(data_points, key=lambda x: (x.get('sector_name', ''), x.get('year', 0))):
            writer.writerow({
                'sector': dp.get('sector_name', ''),
                'market_size_usd_billions': dp.get('value'),
                'year': dp.get('year'),
                'source_name': dp.get('source_name', ''),
                'source_url': dp.get('source_url', ''),
                'confidence': dp.get('confidence', ''),
                'notes': dp.get('notes', '')
            })

    print(f"Exported {len(data_points)} market sizes to: {output_path}")
    return str(output_path)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export Robotics Intelligence Database to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_csv.py                           # Export all data points
  python export_csv.py --summary                 # Export summary by sector/dimension
  python export_csv.py --growth-rates            # Export just growth rates
  python export_csv.py --market-sizes            # Export just market sizes
  python export_csv.py --sector "Mobile Robotics"
  python export_csv.py --validated-only
  python export_csv.py --output my_data.csv
        """
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Export summary statistics instead of raw data"
    )
    parser.add_argument(
        "--growth-rates",
        action="store_true",
        help="Export only growth rate data"
    )
    parser.add_argument(
        "--market-sizes",
        action="store_true",
        help="Export only market size data"
    )
    parser.add_argument(
        "--sector", "-s",
        type=str,
        default=None,
        help="Filter by sector name"
    )
    parser.add_argument(
        "--dimension", "-d",
        type=str,
        default=None,
        help="Filter by dimension name"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=None,
        help="Filter by year"
    )
    parser.add_argument(
        "--validated-only",
        action="store_true",
        help="Only export validated data points"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.summary:
        export_summary_to_csv(args.output)
    elif args.growth_rates:
        export_growth_rates_to_csv(args.output)
    elif args.market_sizes:
        export_market_sizes_to_csv(args.output)
    else:
        export_data_points_to_csv(
            output_path=args.output,
            sector_filter=args.sector,
            dimension_filter=args.dimension,
            year_filter=args.year,
            validated_only=args.validated_only
        )


if __name__ == "__main__":
    main()
