"""
Search module for Robotics Intelligence Database.

Provides Brave Search API integration for web research,
with rate limiting and result parsing.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests

from .config import (
    BRAVE_API_KEY,
    BRAVE_SEARCH_URL,
    BRAVE_RATE_LIMIT_DELAY
)

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result."""

    def __init__(self, title: str, url: str, description: str,
                 source: str = None, published_date: str = None):
        self.title = title
        self.url = url
        self.description = description
        self.source = source
        self.published_date = published_date
        self.fetched_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "description": self.description,
            "source": self.source,
            "published_date": self.published_date,
            "fetched_at": self.fetched_at
        }

    def to_context_string(self) -> str:
        """Format for AI context."""
        return f"Title: {self.title}\nURL: {self.url}\nInfo: {self.description}"


class BraveSearch:
    """Brave Search API client with rate limiting."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Brave Search client.

        Args:
            api_key: Brave API key. Defaults to config value.
        """
        self.api_key = api_key or BRAVE_API_KEY
        self.last_request_time = 0
        self.total_queries = 0

        if not self.api_key:
            logger.warning("Brave API key not configured - search disabled")

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < BRAVE_RATE_LIMIT_DELAY:
            time.sleep(BRAVE_RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def search(self, query: str, count: int = 10) -> List[SearchResult]:
        """
        Execute a search query.

        Args:
            query: Search query string
            count: Number of results to return (max 20)

        Returns:
            list: List of SearchResult objects
        """
        if not self.is_configured:
            logger.error("Search attempted without API key")
            return []

        self._rate_limit()

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key
        }
        params = {
            "q": query,
            "count": min(count, 20)
        }

        try:
            response = requests.get(
                BRAVE_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            self.total_queries += 1

            results = []
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    source=item.get("profile", {}).get("name"),
                    published_date=item.get("age")
                ))

            logger.info(f"Search '{query[:50]}...' returned {len(results)} results")
            return results

        except requests.exceptions.Timeout:
            logger.error(f"Search timeout for query: {query}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Search error for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected search error: {e}")
            return []

    def search_multiple(self, queries: List[str], count_per_query: int = 10,
                        deduplicate: bool = True) -> List[SearchResult]:
        """
        Execute multiple search queries.

        Args:
            queries: List of search query strings
            count_per_query: Results per query
            deduplicate: Remove duplicate URLs

        Returns:
            list: Combined list of SearchResult objects
        """
        all_results = []
        seen_urls = set()

        for query in queries:
            results = self.search(query, count_per_query)

            for result in results:
                if deduplicate and result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                all_results.append(result)

        logger.info(f"Multi-search: {len(queries)} queries, {len(all_results)} unique results")
        return all_results

    def search_robotics_topic(self, topic: str, year: int = None) -> List[SearchResult]:
        """
        Search for robotics-specific topic with domain expertise.

        Args:
            topic: Topic to research
            year: Optional year filter

        Returns:
            list: Search results
        """
        year_str = str(year) if year else "2025"

        queries = [
            f"{topic} robotics market size {year_str}",
            f"{topic} automation industry report {year_str}",
            f"{topic} robot deployment statistics",
            f"{topic} robotics companies funding investment",
            f"{topic} automation ROI case study"
        ]

        return self.search_multiple(queries, count_per_query=5)


class SearchQueryBuilder:
    """Helper to build effective search queries for robotics research."""

    # Query templates for different research types
    TEMPLATES = {
        "market_size": [
            "{sector} market size {year}",
            "{sector} industry revenue {year}",
            "{sector} market forecast projection {year}",
            "global {sector} market report {year}"
        ],
        "growth_rate": [
            "{sector} market growth rate CAGR",
            "{sector} industry growth projection {year}",
            "{sector} market expansion forecast"
        ],
        "companies": [
            "{sector} leading companies market share",
            "{sector} top manufacturers vendors",
            "{sector} competitive landscape analysis",
            "{sector} startups funding {year}"
        ],
        "technology": [
            "{sector} technology capabilities specifications",
            "{sector} technical features comparison",
            "{sector} AI machine learning integration",
            "{sector} innovation trends {year}"
        ],
        "use_cases": [
            "{sector} use cases applications",
            "{sector} deployment case study ROI",
            "{sector} implementation success stories",
            "{sector} industry adoption examples"
        ],
        "pricing": [
            "{sector} pricing cost analysis",
            "{sector} average selling price ASP",
            "{sector} total cost ownership TCO"
        ],
        "regulations": [
            "{sector} regulations standards compliance",
            "{sector} safety standards ISO",
            "{sector} policy government incentives"
        ],
        "trends": [
            "{sector} trends predictions {year}",
            "{sector} future outlook forecast",
            "{sector} emerging technology innovations"
        ]
    }

    @classmethod
    def build_queries(cls, sector: str, research_type: str,
                      year: int = None) -> List[str]:
        """
        Build search queries for a research type.

        Args:
            sector: Robotics sector name
            research_type: Type of research (market_size, companies, etc.)
            year: Optional year for time-sensitive queries

        Returns:
            list: List of formatted query strings
        """
        templates = cls.TEMPLATES.get(research_type, [])
        year_str = str(year) if year else "2025"

        queries = []
        for template in templates:
            query = template.format(sector=sector, year=year_str)
            queries.append(query)

        return queries

    @classmethod
    def build_comprehensive_queries(cls, sector: str, year: int = None) -> Dict[str, List[str]]:
        """
        Build queries for all research types.

        Args:
            sector: Robotics sector name
            year: Optional year

        Returns:
            dict: Research type -> list of queries
        """
        return {
            research_type: cls.build_queries(sector, research_type, year)
            for research_type in cls.TEMPLATES.keys()
        }


def results_to_context(results: List[SearchResult], max_results: int = 30) -> str:
    """
    Convert search results to context string for AI analysis.

    Args:
        results: List of SearchResult objects
        max_results: Maximum results to include

    Returns:
        str: Formatted context string
    """
    context_parts = []
    for result in results[:max_results]:
        context_parts.append(result.to_context_string())
    return "\n\n".join(context_parts)


# Convenience function
def quick_search(query: str, count: int = 10) -> List[Dict[str, Any]]:
    """
    Quick search returning dictionaries.

    Args:
        query: Search query
        count: Number of results

    Returns:
        list: List of result dictionaries
    """
    searcher = BraveSearch()
    results = searcher.search(query, count)
    return [r.to_dict() for r in results]


if __name__ == "__main__":
    # Test search functionality
    logging.basicConfig(level=logging.INFO)

    searcher = BraveSearch()
    if searcher.is_configured:
        results = searcher.search("industrial robotics market size 2025", count=5)
        for r in results:
            print(f"- {r.title}")
            print(f"  {r.url}")
            print()
    else:
        print("Search not configured - set BRAVE_API_KEY in .env")
