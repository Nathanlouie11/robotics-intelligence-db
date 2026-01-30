"""
Configuration management for Robotics Intelligence Database.

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"
RAW_DIR = DATA_DIR / "raw"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "robotics.db"))

# Brave Search configuration
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_RATE_LIMIT_DELAY = 1.0  # seconds between requests

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
OLLAMA_TIMEOUT = 120  # seconds
OLLAMA_TEMPERATURE = 0.3  # Lower for more structured output
OLLAMA_MAX_TOKENS = 4000

# Export configuration
EXPORT_PATH = os.getenv("EXPORT_PATH", str(EXPORTS_DIR))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validation workflow settings
VALIDATION_STATES = [
    "pending",      # Newly ingested, awaiting review
    "in_review",    # Currently being reviewed
    "validated",    # Confirmed accurate
    "rejected",     # Data rejected as inaccurate
    "outdated"      # Previously valid, now superseded
]

# Data point confidence levels
CONFIDENCE_LEVELS = [
    "high",         # Multiple corroborating sources
    "medium",       # Single reliable source
    "low",          # Uncorroborated or older source
    "unverified"    # No source verification
]

# Sector taxonomy - predefined sectors for robotics industry
DEFAULT_SECTORS = [
    {
        "name": "Industrial Robotics",
        "description": "Manufacturing and industrial automation robots",
        "subcategories": [
            "Articulated Robots",
            "SCARA Robots",
            "Delta Robots",
            "Cartesian Robots",
            "Collaborative Robots (Cobots)"
        ]
    },
    {
        "name": "Mobile Robotics",
        "description": "Autonomous mobile robots and vehicles",
        "subcategories": [
            "Autonomous Mobile Robots (AMR)",
            "Automated Guided Vehicles (AGV)",
            "Autonomous Delivery Robots",
            "Drones/UAVs"
        ]
    },
    {
        "name": "Service Robotics",
        "description": "Robots for service and consumer applications",
        "subcategories": [
            "Healthcare Robots",
            "Hospitality Robots",
            "Cleaning Robots",
            "Security Robots",
            "Personal/Consumer Robots"
        ]
    },
    {
        "name": "Agricultural Robotics",
        "description": "Robots for farming and agriculture",
        "subcategories": [
            "Harvesting Robots",
            "Weeding Robots",
            "Planting Robots",
            "Livestock Robots",
            "Crop Monitoring Drones"
        ]
    },
    {
        "name": "Logistics Robotics",
        "description": "Warehouse and supply chain automation",
        "subcategories": [
            "Pick and Place Robots",
            "Sorting Robots",
            "Palletizing Robots",
            "Inventory Robots",
            "Last-Mile Delivery"
        ]
    },
    {
        "name": "Construction Robotics",
        "description": "Robots for construction and building",
        "subcategories": [
            "Bricklaying Robots",
            "3D Printing Robots",
            "Demolition Robots",
            "Inspection Robots",
            "Exoskeletons"
        ]
    }
]

# Data dimensions - what metrics we track
DEFAULT_DIMENSIONS = [
    {"name": "market_size", "unit": "USD billions", "description": "Total addressable market size"},
    {"name": "market_growth_rate", "unit": "percent", "description": "Year-over-year growth rate"},
    {"name": "unit_shipments", "unit": "units", "description": "Number of units shipped"},
    {"name": "average_selling_price", "unit": "USD", "description": "Average unit price"},
    {"name": "deployment_count", "unit": "units", "description": "Installed base / deployments"},
    {"name": "roi_payback_period", "unit": "months", "description": "Typical ROI payback period"},
    {"name": "labor_productivity_gain", "unit": "percent", "description": "Productivity improvement"},
    {"name": "adoption_rate", "unit": "percent", "description": "Market penetration rate"},
    {"name": "funding_raised", "unit": "USD millions", "description": "VC/investment funding"},
    {"name": "employee_count", "unit": "employees", "description": "Company workforce size"}
]


def validate_config() -> dict:
    """
    Validate configuration and return status.

    Returns:
        dict: Configuration validation results
    """
    issues = []
    warnings = []

    if not BRAVE_API_KEY:
        issues.append("BRAVE_API_KEY not set - research features disabled")

    if not Path(DATABASE_PATH).parent.exists():
        warnings.append(f"Database directory does not exist: {Path(DATABASE_PATH).parent}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "config": {
            "database_path": DATABASE_PATH,
            "ollama_host": OLLAMA_HOST,
            "ollama_model": OLLAMA_MODEL,
            "brave_configured": bool(BRAVE_API_KEY),
            "export_path": EXPORT_PATH
        }
    }


if __name__ == "__main__":
    # Print configuration status when run directly
    import json
    result = validate_config()
    print(json.dumps(result, indent=2))
