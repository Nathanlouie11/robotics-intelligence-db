"""
AI Analysis module for Robotics Intelligence Database.

Provides Ollama integration for analyzing research data and
extracting structured intelligence from unstructured sources.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

import requests

from .config import (
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_TEMPERATURE,
    OLLAMA_MAX_TOKENS
)

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama API interactions."""

    def __init__(self, host: str = None, model: str = None):
        """
        Initialize Ollama client.

        Args:
            host: Ollama server URL. Defaults to config.
            model: Model name. Defaults to config.
        """
        self.host = host or OLLAMA_HOST
        self.model = model or OLLAMA_MODEL
        self.generate_url = f"{self.host}/api/generate"

    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: str = None,
                 temperature: float = None, max_tokens: int = None) -> str:
        """
        Generate text from Ollama.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            str: Generated text
        """
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature or OLLAMA_TEMPERATURE,
                "num_predict": max_tokens or OLLAMA_MAX_TOKENS
            }
        }

        try:
            response = requests.post(
                self.generate_url,
                json=payload,
                timeout=OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            raise


class RoboticsAnalyzer:
    """AI-powered analyzer for robotics intelligence data."""

    # System prompts for different analysis types
    SYSTEM_PROMPTS = {
        "extract_data": """You are a data extraction specialist for robotics industry intelligence.
Your task is to extract structured data from search results.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON - no prose, no explanations, no markdown
2. Extract specific numeric values with their units
3. Include source URLs for each data point
4. Express confidence as: high, medium, low, or unverified
5. Use null for missing values, never make up data

Output format must be a JSON object.""",

        "analyze_market": """You are a robotics market analyst.
Extract market intelligence and output ONLY valid JSON.

Required fields:
- market_size_usd_billions: number or null
- growth_rate_percent: number or null
- year: number
- key_players: array of company names
- trends: array of trend descriptions
- sources: array of source URLs

Do not include any text outside the JSON object.""",

        "analyze_company": """You are a robotics company analyst.
Extract company intelligence and output ONLY valid JSON.

Required fields:
- company_name: string
- products: array of product names
- market_position: string description
- funding_usd_millions: number or null
- employee_count: number or null
- key_differentiators: array of strings
- sources: array of source URLs

Do not include any text outside the JSON object.""",

        "summarize": """You are a robotics intelligence summarizer.
Provide a brief, factual summary based on the provided context.
Focus on key data points, trends, and actionable insights.
Keep the summary under 300 words."""
    }

    def __init__(self, client: OllamaClient = None):
        """
        Initialize analyzer.

        Args:
            client: OllamaClient instance. Creates new one if not provided.
        """
        self.client = client or OllamaClient()

    def _clean_json_response(self, response: str) -> str:
        """Extract JSON from response, handling common issues."""
        # Try to find JSON object or array
        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', response)
        if json_match:
            return json_match.group(1)
        return response

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response with error handling."""
        cleaned = self._clean_json_response(response)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return {"raw_response": response, "parse_error": str(e)}

    def extract_data_points(self, context: str, sector: str,
                           dimension: str) -> Dict[str, Any]:
        """
        Extract structured data points from search context.

        Args:
            context: Search results context string
            sector: Robotics sector name
            dimension: Data dimension (e.g., 'market_size')

        Returns:
            dict: Extracted data with structure
        """
        prompt = f"""Extract {dimension} data for {sector} from these sources:

{context}

Output JSON with this structure:
{{
    "sector": "{sector}",
    "dimension": "{dimension}",
    "data_points": [
        {{
            "value": <number or null>,
            "unit": "<unit string>",
            "year": <year number>,
            "quarter": <1-4 or null>,
            "source_url": "<url>",
            "source_name": "<source name>",
            "confidence": "<high|medium|low|unverified>",
            "notes": "<any relevant context>"
        }}
    ],
    "extraction_timestamp": "{datetime.now().isoformat()}"
}}

Extract ALL relevant data points found. Use null for missing values."""

        response = self.client.generate(
            prompt,
            system_prompt=self.SYSTEM_PROMPTS["extract_data"],
            temperature=0.1  # Low temperature for structured output
        )

        return self._parse_json_response(response)

    def analyze_market(self, context: str, sector: str,
                       year: int = None) -> Dict[str, Any]:
        """
        Analyze market data for a sector.

        Args:
            context: Search results context
            sector: Robotics sector
            year: Target year for analysis

        Returns:
            dict: Market analysis results
        """
        year = year or datetime.now().year

        prompt = f"""Analyze market data for {sector} in {year}:

{context}

Output JSON:
{{
    "sector": "{sector}",
    "year": {year},
    "market_size": {{
        "value_usd_billions": <number or null>,
        "confidence": "<high|medium|low>",
        "source": "<url>"
    }},
    "growth_rate": {{
        "cagr_percent": <number or null>,
        "yoy_percent": <number or null>,
        "forecast_period": "<e.g., 2024-2030>",
        "source": "<url>"
    }},
    "market_segments": [
        {{
            "name": "<segment>",
            "share_percent": <number or null>
        }}
    ],
    "key_players": [
        {{
            "company": "<name>",
            "market_share_percent": <number or null>,
            "headquarters": "<country>"
        }}
    ],
    "trends": ["<trend 1>", "<trend 2>"],
    "challenges": ["<challenge 1>"],
    "sources_analyzed": <count>
}}"""

        response = self.client.generate(
            prompt,
            system_prompt=self.SYSTEM_PROMPTS["analyze_market"],
            temperature=0.2
        )

        return self._parse_json_response(response)

    def analyze_company(self, context: str, company_name: str) -> Dict[str, Any]:
        """
        Analyze a specific robotics company.

        Args:
            context: Search results context
            company_name: Company to analyze

        Returns:
            dict: Company analysis
        """
        prompt = f"""Analyze company data for {company_name}:

{context}

Output JSON:
{{
    "company_name": "{company_name}",
    "overview": {{
        "description": "<brief description>",
        "founded_year": <year or null>,
        "headquarters": "<location>",
        "website": "<url or null>"
    }},
    "financials": {{
        "revenue_usd_millions": <number or null>,
        "funding_raised_usd_millions": <number or null>,
        "valuation_usd_millions": <number or null>,
        "employee_count": <number or null>
    }},
    "products": [
        {{
            "name": "<product>",
            "category": "<category>",
            "key_features": ["<feature>"]
        }}
    ],
    "market_position": {{
        "market_share_percent": <number or null>,
        "competitive_advantages": ["<advantage>"],
        "target_industries": ["<industry>"]
    }},
    "recent_developments": ["<development>"],
    "sources": ["<url>"]
}}"""

        response = self.client.generate(
            prompt,
            system_prompt=self.SYSTEM_PROMPTS["analyze_company"],
            temperature=0.2
        )

        return self._parse_json_response(response)

    def analyze_technology(self, context: str, technology: str) -> Dict[str, Any]:
        """
        Analyze a robotics technology.

        Args:
            context: Search results context
            technology: Technology to analyze

        Returns:
            dict: Technology analysis
        """
        prompt = f"""Analyze technology: {technology}

{context}

Output JSON:
{{
    "technology": "{technology}",
    "maturity_level": "<emerging|growing|mature|declining>",
    "description": "<technical description>",
    "capabilities": [
        {{
            "capability": "<name>",
            "current_state": "<description>",
            "limitations": ["<limitation>"]
        }}
    ],
    "applications": [
        {{
            "industry": "<industry>",
            "use_cases": ["<use case>"],
            "adoption_level": "<early|growing|mainstream>"
        }}
    ],
    "key_metrics": {{
        "accuracy_percent": <number or null>,
        "speed": "<description>",
        "cost_trend": "<decreasing|stable|increasing>"
    }},
    "leading_providers": ["<company>"],
    "future_outlook": "<prediction>",
    "sources": ["<url>"]
}}"""

        response = self.client.generate(
            prompt,
            system_prompt=self.SYSTEM_PROMPTS["extract_data"],
            temperature=0.2
        )

        return self._parse_json_response(response)

    def summarize(self, context: str, focus: str = None) -> str:
        """
        Generate a summary of research context.

        Args:
            context: Research context to summarize
            focus: Optional focus area

        Returns:
            str: Summary text
        """
        focus_instruction = f"Focus on: {focus}" if focus else ""

        prompt = f"""Summarize this robotics intelligence:

{context}

{focus_instruction}

Provide a concise summary with key facts and figures."""

        return self.client.generate(
            prompt,
            system_prompt=self.SYSTEM_PROMPTS["summarize"],
            temperature=0.3
        )

    def extract_interview_insights(self, transcript: str,
                                   expert_name: str) -> Dict[str, Any]:
        """
        Extract structured insights from an interview transcript.

        Args:
            transcript: Interview transcript text
            expert_name: Name of the expert

        Returns:
            dict: Extracted insights
        """
        prompt = f"""Extract insights from this interview with {expert_name}:

{transcript}

Output JSON:
{{
    "expert": "{expert_name}",
    "key_insights": [
        {{
            "topic": "<topic>",
            "insight": "<insight text>",
            "quote": "<direct quote if available>",
            "importance": "<high|medium|low>"
        }}
    ],
    "market_predictions": [
        {{
            "prediction": "<prediction>",
            "timeframe": "<timeframe>",
            "confidence": "<high|medium|low>"
        }}
    ],
    "company_mentions": [
        {{
            "company": "<name>",
            "context": "<positive|negative|neutral>",
            "details": "<what was said>"
        }}
    ],
    "technology_mentions": ["<technology>"],
    "action_items": ["<follow-up item>"],
    "summary": "<2-3 sentence summary>"
}}"""

        response = self.client.generate(
            prompt,
            system_prompt=self.SYSTEM_PROMPTS["extract_data"],
            temperature=0.2
        )

        return self._parse_json_response(response)


def analyze_with_ollama(prompt: str, context: str = "") -> str:
    """
    Simple function to analyze with Ollama.

    Args:
        prompt: Analysis prompt
        context: Optional context

    Returns:
        str: Analysis result
    """
    client = OllamaClient()
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    return client.generate(full_prompt)


if __name__ == "__main__":
    # Test Ollama connection
    logging.basicConfig(level=logging.INFO)

    client = OllamaClient()
    if client.is_available():
        print(f"Ollama available at {client.host}")
        print(f"Model: {client.model}")

        # Quick test
        response = client.generate("What is 2+2? Reply with just the number.")
        print(f"Test response: {response}")
    else:
        print(f"Ollama not available at {client.host}")
