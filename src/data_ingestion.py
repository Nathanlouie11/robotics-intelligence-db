"""
Data Ingestion module for Robotics Intelligence Database.

Handles automated research sessions that combine search, AI analysis,
and database storage to build the intelligence database.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from .config import BRAVE_RATE_LIMIT_DELAY
from .database import Database
from .search import BraveSearch, SearchQueryBuilder, results_to_context
from .ai_analysis import RoboticsAnalyzer, OllamaClient

logger = logging.getLogger(__name__)


class ResearchSession:
    """Manages an automated research session."""

    def __init__(self, db: Database = None, searcher: BraveSearch = None,
                 analyzer: RoboticsAnalyzer = None):
        """
        Initialize research session.

        Args:
            db: Database instance
            searcher: BraveSearch instance
            analyzer: RoboticsAnalyzer instance
        """
        self.db = db or Database()
        self.searcher = searcher or BraveSearch()
        self.analyzer = analyzer or RoboticsAnalyzer()

        self.session_id = None
        self.queries_run = 0
        self.sources_found = 0
        self.data_points_created = 0

    def _update_session(self, status: str = None, error: str = None):
        """Update session tracking in database."""
        if self.session_id:
            self.db.update_research_session(
                self.session_id,
                queries_run=self.queries_run,
                sources_found=self.sources_found,
                data_points_created=self.data_points_created,
                status=status,
                error_message=error
            )

    def research_sector(self, sector_name: str, year: int = None,
                        research_types: List[str] = None) -> Dict[str, Any]:
        """
        Conduct comprehensive research on a robotics sector.

        Args:
            sector_name: Name of sector to research
            year: Target year for data
            research_types: List of research types to perform.
                           Defaults to all types.

        Returns:
            dict: Research results with extracted data
        """
        year = year or datetime.now().year
        research_types = research_types or [
            "market_size", "growth_rate", "companies",
            "technology", "use_cases", "trends"
        ]

        logger.info(f"Starting sector research: {sector_name}")

        # Start tracking session
        self.session_id = self.db.start_research_session(
            "sector_deep_dive", sector_name
        )

        results = {
            "sector": sector_name,
            "year": year,
            "research_started": datetime.now().isoformat(),
            "phases": {},
            "data_points_extracted": [],
            "errors": []
        }

        try:
            for research_type in research_types:
                logger.info(f"Phase: {research_type}")
                phase_result = self._research_phase(
                    sector_name, research_type, year
                )
                results["phases"][research_type] = phase_result

                # Extract and store data points
                if "data_points" in phase_result.get("analysis", {}):
                    for dp in phase_result["analysis"]["data_points"]:
                        try:
                            self._store_data_point(sector_name, research_type, dp)
                            results["data_points_extracted"].append(dp)
                        except Exception as e:
                            logger.warning(f"Failed to store data point: {e}")
                            results["errors"].append(str(e))

            results["research_completed"] = datetime.now().isoformat()
            results["summary"] = {
                "queries_run": self.queries_run,
                "sources_found": self.sources_found,
                "data_points_created": self.data_points_created
            }

            self._update_session(status="completed")

        except Exception as e:
            logger.error(f"Research session failed: {e}")
            results["error"] = str(e)
            self._update_session(status="failed", error=str(e))
            raise

        return results

    def _research_phase(self, sector: str, research_type: str,
                        year: int) -> Dict[str, Any]:
        """
        Execute a single research phase.

        Args:
            sector: Sector name
            research_type: Type of research
            year: Target year

        Returns:
            dict: Phase results
        """
        # Build queries for this phase
        queries = SearchQueryBuilder.build_queries(sector, research_type, year)

        # Execute searches
        all_results = []
        for query in queries:
            logger.debug(f"Searching: {query[:60]}...")
            results = self.searcher.search(query, count=10)
            all_results.extend(results)
            self.queries_run += 1

        self.sources_found += len(all_results)
        self._update_session()

        # Build context for analysis
        context = results_to_context(all_results, max_results=25)

        # Map research type to dimension
        dimension_map = {
            "market_size": "market_size",
            "growth_rate": "market_growth_rate",
            "companies": "market_size",  # Will extract company data
            "technology": "adoption_rate",
            "use_cases": "roi_payback_period",
            "trends": "market_growth_rate",
            "pricing": "average_selling_price"
        }
        dimension = dimension_map.get(research_type, "market_size")

        # Analyze with AI
        analysis = {}
        if context:
            try:
                if research_type == "market_size":
                    analysis = self.analyzer.analyze_market(context, sector, year)
                elif research_type == "companies":
                    # Extract company data from market analysis
                    analysis = self.analyzer.analyze_market(context, sector, year)
                else:
                    analysis = self.analyzer.extract_data_points(
                        context, sector, dimension
                    )
            except Exception as e:
                logger.warning(f"Analysis failed for {research_type}: {e}")
                analysis = {"error": str(e)}

        return {
            "research_type": research_type,
            "queries": queries,
            "sources_count": len(all_results),
            "sources": [r.to_dict() for r in all_results[:10]],  # Top 10
            "analysis": analysis
        }

    def _store_data_point(self, sector: str, research_type: str,
                          data_point: Dict[str, Any]):
        """Store a single data point in the database."""
        # Determine dimension from research type
        dimension_map = {
            "market_size": "market_size",
            "growth_rate": "market_growth_rate",
            "unit_shipments": "unit_shipments",
            "pricing": "average_selling_price",
            "adoption": "adoption_rate",
            "roi": "roi_payback_period",
            "funding": "funding_raised"
        }
        dimension = dimension_map.get(research_type, "market_size")

        # Get or create source
        source_id = None
        if data_point.get("source_url"):
            source_id = self.db.get_or_create_source(
                name=data_point.get("source_name", "Web Source"),
                url=data_point.get("source_url"),
                source_type="research_report"
            )

        # Add data point
        dp_id = self.db.add_data_point(
            dimension_name=dimension,
            value=data_point.get("value"),
            sector_name=sector,
            year=data_point.get("year"),
            quarter=data_point.get("quarter"),
            source_id=source_id,
            confidence=data_point.get("confidence", "medium"),
            notes=data_point.get("notes"),
            metadata={"raw_extraction": data_point}
        )

        self.data_points_created += 1
        self._update_session()

        return dp_id

    def research_company(self, company_name: str) -> Dict[str, Any]:
        """
        Research a specific robotics company.

        Args:
            company_name: Company to research

        Returns:
            dict: Company research results
        """
        logger.info(f"Researching company: {company_name}")

        self.session_id = self.db.start_research_session(
            "company_research", company_name
        )

        queries = [
            f"{company_name} robotics company profile",
            f"{company_name} funding investment valuation",
            f"{company_name} products robots automation",
            f"{company_name} revenue employees growth",
            f"{company_name} news announcements 2025"
        ]

        all_results = []
        for query in queries:
            results = self.searcher.search(query, count=8)
            all_results.extend(results)
            self.queries_run += 1

        self.sources_found = len(all_results)
        self._update_session()

        context = results_to_context(all_results, max_results=30)

        analysis = {}
        if context:
            try:
                analysis = self.analyzer.analyze_company(context, company_name)
            except Exception as e:
                logger.warning(f"Company analysis failed: {e}")
                analysis = {"error": str(e)}

        self._update_session(status="completed")

        return {
            "company": company_name,
            "research_timestamp": datetime.now().isoformat(),
            "queries_run": self.queries_run,
            "sources_found": self.sources_found,
            "sources": [r.to_dict() for r in all_results[:15]],
            "analysis": analysis
        }

    def research_technology(self, technology_name: str) -> Dict[str, Any]:
        """
        Research a specific robotics technology.

        Args:
            technology_name: Technology to research

        Returns:
            dict: Technology research results
        """
        logger.info(f"Researching technology: {technology_name}")

        self.session_id = self.db.start_research_session(
            "technology_research", technology_name
        )

        # Ensure technology exists in database
        tech = self.db.get_technology_by_name(technology_name)
        if not tech:
            # Add as new technology with default category
            self.db.add_technology(
                name=technology_name,
                category="emerging",
                description=f"Auto-added from research: {technology_name}"
            )

        queries = [
            f"{technology_name} robotics market size 2025 2026",
            f"{technology_name} robotics market growth CAGR",
            f"{technology_name} robotics technology overview capabilities",
            f"{technology_name} robotics applications use cases",
            f"{technology_name} robotics leading companies vendors",
            f"{technology_name} robotics adoption trends statistics",
            f"{technology_name} robotics investment funding"
        ]

        all_results = []
        for query in queries:
            results = self.searcher.search(query, count=8)
            all_results.extend(results)
            self.queries_run += 1

        self.sources_found = len(all_results)
        self._update_session()

        context = results_to_context(all_results, max_results=30)

        # Analyze with AI
        analysis = {}
        if context:
            try:
                analysis = self.analyzer.analyze_technology(context, technology_name)

                # Store extracted data points
                self._store_technology_data_points(technology_name, analysis, all_results)

            except Exception as e:
                logger.warning(f"Technology analysis failed: {e}")
                analysis = {"error": str(e)}

        self._update_session(status="completed")

        return {
            "technology": technology_name,
            "research_timestamp": datetime.now().isoformat(),
            "queries_run": self.queries_run,
            "sources_found": self.sources_found,
            "data_points_created": self.data_points_created,
            "sources": [r.to_dict() for r in all_results[:15]],
            "analysis": analysis
        }

    def _store_technology_data_points(self, technology_name: str,
                                       analysis: Dict, sources: List):
        """Store extracted technology data points."""
        try:
            # Store market size if found
            if "market_size" in str(analysis):
                # Try to extract from analysis
                pass  # AI already extracts structured data

            # Store any structured data from analysis
            if isinstance(analysis, dict) and not analysis.get("error"):
                # Store the analysis as a data point
                source_id = None
                if sources:
                    source_id = self.db.get_or_create_source(
                        name=sources[0].title if hasattr(sources[0], 'title') else "Research",
                        url=sources[0].url if hasattr(sources[0], 'url') else None,
                        source_type="research_report"
                    )

                # Store market growth rate if available
                if analysis.get("key_metrics"):
                    self.db.add_technology_data_point(
                        technology_name=technology_name,
                        dimension_name="market_growth_rate",
                        value=analysis,
                        year=datetime.now().year,
                        source_id=source_id,
                        confidence="medium",
                        notes="Extracted from technology research"
                    )
                    self.data_points_created += 1

        except Exception as e:
            logger.warning(f"Failed to store technology data points: {e}")


class DataIngestionPipeline:
    """
    Pipeline for ingesting data from various sources.
    """

    def __init__(self, db: Database = None):
        """
        Initialize pipeline.

        Args:
            db: Database instance
        """
        self.db = db or Database()

    def ingest_manual_data_point(self, data: Dict[str, Any]) -> int:
        """
        Ingest a manually provided data point.

        Args:
            data: Data point dictionary with required fields:
                  - dimension: dimension name
                  - value: the value
                  - sector: optional sector name
                  - year: optional year
                  - source_name: optional source name
                  - source_url: optional source URL

        Returns:
            int: ID of created data point
        """
        # Validate required fields
        if "dimension" not in data or "value" not in data:
            raise ValueError("dimension and value are required")

        # Handle source
        source_id = None
        if data.get("source_url") or data.get("source_name"):
            source_id = self.db.get_or_create_source(
                name=data.get("source_name", "Manual Entry"),
                url=data.get("source_url"),
                source_type="manual"
            )

        return self.db.add_data_point(
            dimension_name=data["dimension"],
            value=data["value"],
            sector_name=data.get("sector"),
            subcategory_name=data.get("subcategory"),
            year=data.get("year"),
            quarter=data.get("quarter"),
            month=data.get("month"),
            source_id=source_id,
            confidence=data.get("confidence", "medium"),
            notes=data.get("notes")
        )

    def ingest_bulk_data(self, data_points: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest multiple data points.

        Args:
            data_points: List of data point dictionaries

        Returns:
            dict: Counts of successful and failed ingestions
        """
        successful = 0
        failed = 0
        errors = []

        for dp in data_points:
            try:
                self.ingest_manual_data_point(dp)
                successful += 1
            except Exception as e:
                failed += 1
                errors.append({"data": dp, "error": str(e)})

        return {
            "successful": successful,
            "failed": failed,
            "errors": errors
        }

    def ingest_interview(self, interview_data: Dict[str, Any]) -> int:
        """
        Ingest an interview record.

        Args:
            interview_data: Interview dictionary with fields:
                           - expert_name: required
                           - expert_title: optional
                           - expert_company: optional
                           - interview_date: optional
                           - transcript: optional (for AI extraction)
                           - key_insights: optional list

        Returns:
            int: ID of created interview
        """
        # If transcript provided, extract insights with AI
        key_insights = interview_data.get("key_insights", [])
        summary = interview_data.get("summary")

        if interview_data.get("transcript") and not key_insights:
            try:
                analyzer = RoboticsAnalyzer()
                extraction = analyzer.extract_interview_insights(
                    interview_data["transcript"],
                    interview_data["expert_name"]
                )
                if "key_insights" in extraction:
                    key_insights = [
                        i.get("insight") for i in extraction["key_insights"]
                    ]
                if "summary" in extraction:
                    summary = extraction["summary"]
            except Exception as e:
                logger.warning(f"Interview extraction failed: {e}")

        return self.db.add_interview(
            expert_name=interview_data["expert_name"],
            expert_title=interview_data.get("expert_title"),
            expert_company=interview_data.get("expert_company"),
            interview_date=interview_data.get("interview_date"),
            topics=interview_data.get("topics"),
            key_insights=key_insights,
            summary=summary,
            metadata={"original_data": interview_data}
        )


def run_sector_research(sector: str, year: int = None) -> Dict[str, Any]:
    """
    Convenience function to run sector research.

    Args:
        sector: Sector name
        year: Target year

    Returns:
        dict: Research results
    """
    session = ResearchSession()
    return session.research_sector(sector, year)


def run_company_research(company: str) -> Dict[str, Any]:
    """
    Convenience function to run company research.

    Args:
        company: Company name

    Returns:
        dict: Research results
    """
    session = ResearchSession()
    return session.research_company(company)


if __name__ == "__main__":
    # Test research session
    logging.basicConfig(level=logging.INFO)

    # Initialize database
    db = Database()
    db.seed_default_data()

    # Run a small test
    session = ResearchSession(db)

    # Check if services are available
    if not session.searcher.is_configured:
        print("Warning: Brave Search not configured")
    if not session.analyzer.client.is_available():
        print("Warning: Ollama not available")

    print("Research session initialized")
    print(f"Database has {db.get_statistics()['sectors_count']} sectors")
