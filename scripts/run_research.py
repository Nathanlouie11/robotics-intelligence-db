#!/usr/bin/env python3
"""
Run Research Script for Robotics Intelligence Database.

Command-line tool to execute research sessions and populate
the database with intelligence data.

Usage:
    python run_research.py sector "Industrial Robotics"
    python run_research.py company "Boston Dynamics"
    python run_research.py technology "Computer Vision"
    python run_research.py all-sectors
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
from src.data_ingestion import ResearchSession, run_sector_research, run_company_research
from src.config import validate_config, DEFAULT_SECTORS


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def check_prerequisites():
    """Check if required services are available."""
    config = validate_config()

    if not config["valid"]:
        print("Configuration issues:")
        for issue in config["issues"]:
            print(f"  - {issue}")
        return False

    if config["warnings"]:
        print("Warnings:")
        for warning in config["warnings"]:
            print(f"  - {warning}")

    # Check Ollama
    from src.ai_analysis import OllamaClient
    client = OllamaClient()
    if not client.is_available():
        print(f"ERROR: Ollama not available at {client.host}")
        print("Start Ollama with: ollama serve")
        return False

    # Check Brave API
    from src.search import BraveSearch
    searcher = BraveSearch()
    if not searcher.is_configured:
        print("ERROR: BRAVE_API_KEY not configured")
        print("Set BRAVE_API_KEY in .env file")
        return False

    print("All prerequisites met")
    return True


def research_sector(sector_name: str, year: int = None, output_file: str = None):
    """
    Run research on a sector.

    Args:
        sector_name: Name of sector to research
        year: Target year
        output_file: Optional output file path
    """
    print(f"\n{'='*60}")
    print(f"SECTOR RESEARCH: {sector_name.upper()}")
    print(f"{'='*60}")

    session = ResearchSession()

    print(f"\nStarting research session...")
    print(f"  Target year: {year or 'current'}")
    print(f"  Research phases: market_size, growth_rate, companies, technology, use_cases, trends")
    print()

    try:
        results = session.research_sector(sector_name, year)

        print(f"\n{'='*60}")
        print("RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"  Queries run: {results['summary']['queries_run']}")
        print(f"  Sources found: {results['summary']['sources_found']}")
        print(f"  Data points created: {results['summary']['data_points_created']}")

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"  Results saved to: {output_file}")

        return results

    except Exception as e:
        print(f"\nERROR: Research failed - {e}")
        logging.exception("Research failed")
        return None


def research_company(company_name: str, output_file: str = None):
    """
    Run research on a company.

    Args:
        company_name: Company to research
        output_file: Optional output file path
    """
    print(f"\n{'='*60}")
    print(f"COMPANY RESEARCH: {company_name.upper()}")
    print(f"{'='*60}")

    session = ResearchSession()

    try:
        results = session.research_company(company_name)

        print(f"\n{'='*60}")
        print("RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"  Queries run: {results['queries_run']}")
        print(f"  Sources found: {results['sources_found']}")

        if "analysis" in results and "company_name" in results["analysis"]:
            analysis = results["analysis"]
            print(f"\n  Company: {analysis.get('company_name')}")
            if "overview" in analysis:
                print(f"  Description: {analysis['overview'].get('description', 'N/A')[:100]}...")
            if "financials" in analysis:
                fin = analysis["financials"]
                if fin.get("funding_raised_usd_millions"):
                    print(f"  Funding: ${fin['funding_raised_usd_millions']}M")
                if fin.get("employee_count"):
                    print(f"  Employees: {fin['employee_count']}")

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n  Results saved to: {output_file}")

        return results

    except Exception as e:
        print(f"\nERROR: Research failed - {e}")
        logging.exception("Research failed")
        return None


def research_technology(tech_name: str, output_file: str = None):
    """
    Run research on a technology.

    Args:
        tech_name: Technology to research
        output_file: Optional output file path
    """
    print(f"\n{'='*60}")
    print(f"TECHNOLOGY RESEARCH: {tech_name.upper()}")
    print(f"{'='*60}")

    session = ResearchSession()

    try:
        results = session.research_technology(tech_name)

        print(f"\n{'='*60}")
        print("RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"  Queries run: {results['queries_run']}")
        print(f"  Sources found: {results['sources_found']}")

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n  Results saved to: {output_file}")

        return results

    except Exception as e:
        print(f"\nERROR: Research failed - {e}")
        logging.exception("Research failed")
        return None


def research_all_sectors(year: int = None):
    """Research all default sectors."""
    print(f"\n{'='*60}")
    print("RESEARCHING ALL SECTORS")
    print(f"{'='*60}")

    sectors = [s["name"] for s in DEFAULT_SECTORS]
    print(f"Sectors to research: {len(sectors)}")
    for s in sectors:
        print(f"  - {s}")

    results = {}
    for sector in sectors:
        print(f"\n{'='*60}")
        result = research_sector(sector, year)
        if result:
            results[sector] = result
        print(f"Completed: {sector}")

    print(f"\n{'='*60}")
    print("ALL SECTORS COMPLETE")
    print(f"{'='*60}")
    print(f"Sectors researched: {len(results)}/{len(sectors)}")

    return results


def init_database():
    """Initialize database with default data."""
    print("Initializing database...")
    db = Database()
    result = db.seed_default_data()

    print(f"Database initialized:")
    print(f"  Sectors created: {result['sectors_created']}")
    print(f"  Subcategories created: {result['subcategories_created']}")
    print(f"  Dimensions created: {result['dimensions_created']}")

    stats = db.get_statistics()
    print(f"\nDatabase statistics:")
    print(f"  Total sectors: {stats['sectors_count']}")
    print(f"  Total dimensions: {stats['dimensions_count']}")
    print(f"  Total data points: {stats['data_points_count']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Robotics Intelligence Database Research Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_research.py init                      # Initialize database
  python run_research.py sector "Industrial Robotics"
  python run_research.py company "Boston Dynamics"
  python run_research.py technology "Computer Vision"
  python run_research.py all-sectors
  python run_research.py sector "Mobile Robotics" --year 2025 --output results.json
        """
    )

    parser.add_argument(
        "command",
        choices=["init", "sector", "company", "technology", "all-sectors", "check"],
        help="Research command to run"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target to research (sector name, company name, or technology)"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=None,
        help="Target year for research"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path for results"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.command == "check":
        if check_prerequisites():
            print("\nReady to run research!")
        sys.exit(0)

    if args.command == "init":
        init_database()
        sys.exit(0)

    # Check prerequisites for research commands
    if not check_prerequisites():
        sys.exit(1)

    if args.command == "sector":
        if not args.target:
            print("ERROR: Sector name required")
            sys.exit(1)
        research_sector(args.target, args.year, args.output)

    elif args.command == "company":
        if not args.target:
            print("ERROR: Company name required")
            sys.exit(1)
        research_company(args.target, args.output)

    elif args.command == "technology":
        if not args.target:
            print("ERROR: Technology name required")
            sys.exit(1)
        research_technology(args.target, args.output)

    elif args.command == "all-sectors":
        research_all_sectors(args.year)


if __name__ == "__main__":
    main()
