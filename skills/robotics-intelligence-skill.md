# Robotics Intelligence Database Skill

## Overview

This skill manages a structured database of robotics industry intelligence. It combines automated web research (via Brave Search), AI-powered analysis (via local Ollama), and a SQLite database to track market data, company information, and industry trends.

## Capabilities

### 1. Research Operations
- **Sector Research**: Deep-dive research on robotics sectors (Industrial, Mobile, Service, Agricultural, Logistics, Construction)
- **Company Research**: Detailed analysis of robotics companies
- **Technology Research**: Analysis of specific robotics technologies

### 2. Data Management
- Store and retrieve structured data points
- Track data sources and confidence levels
- Manage validation workflow (pending → in_review → validated/rejected)
- Detect changes month-over-month and year-over-year

### 3. Export & Reporting
- Export full database as structured JSON
- Generate sector-specific reports
- Generate dimension analysis reports
- Export time series data
- Validation status reports
- Change detection reports

## Database Schema

### Core Tables
- **sectors**: Top-level industry categories (Industrial Robotics, Mobile Robotics, etc.)
- **subcategories**: Nested categories under sectors
- **dimensions**: Metrics tracked (market_size, growth_rate, unit_shipments, etc.)
- **data_points**: Actual intelligence data with values, sources, and validation status
- **sources**: Data source information with reliability scores
- **changes_log**: Audit trail of all modifications
- **interviews**: Expert interview records

### Dimensions Tracked
- market_size (USD billions)
- market_growth_rate (percent)
- unit_shipments (units)
- average_selling_price (USD)
- deployment_count (units)
- roi_payback_period (months)
- labor_productivity_gain (percent)
- adoption_rate (percent)
- funding_raised (USD millions)
- employee_count (employees)

## Usage Examples

### Initialize Database
```bash
python scripts/run_research.py init
```

### Run Research
```bash
# Research a sector
python scripts/run_research.py sector "Industrial Robotics"

# Research a company
python scripts/run_research.py company "Boston Dynamics"

# Research a technology
python scripts/run_research.py technology "Computer Vision"

# Research all sectors
python scripts/run_research.py all-sectors
```

### Export Data
```bash
# List available data
python scripts/export_json.py list

# Export full database
python scripts/export_json.py full

# Export sector report
python scripts/export_json.py sector "Industrial Robotics"

# Export dimension analysis
python scripts/export_json.py dimension market_size --year 2025

# Export validation status
python scripts/export_json.py validation
```

## Configuration

Environment variables (set in `.env`):
- `BRAVE_API_KEY`: Required for web research
- `OLLAMA_HOST`: Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model to use (default: qwen2.5:32b)
- `DATABASE_PATH`: SQLite database path
- `EXPORT_PATH`: Export directory path

## Output Format

All outputs are structured JSON. Example sector report:

```json
{
  "report_type": "sector_intelligence",
  "sector": "Industrial Robotics",
  "generated_at": "2025-01-30T10:00:00",
  "data_points_count": 45,
  "dimensions": {
    "market_size": [
      {
        "value": 52.3,
        "year": 2025,
        "source": "IFR World Robotics",
        "confidence": "high"
      }
    ],
    "market_growth_rate": [
      {
        "value": 12.5,
        "year": 2025,
        "source": "Markets and Markets",
        "confidence": "medium"
      }
    ]
  },
  "summary": {
    "latest_market_size": {
      "value_usd_billions": 52.3,
      "year": 2025
    }
  }
}
```

## Validation Workflow

Data points go through a validation workflow:

1. **pending**: Newly ingested data awaiting review
2. **in_review**: Currently being reviewed by analyst
3. **validated**: Confirmed accurate
4. **rejected**: Data rejected as inaccurate
5. **outdated**: Previously valid, now superseded

Validation rules check:
- Has source
- Has year
- Value not null
- Reasonable bounds (market size, growth rates)
- Recent year (within 5 years)
- Valid confidence level

## Integration Points

### Python API
```python
from src.database import Database
from src.data_ingestion import ResearchSession
from src.reporting import ReportGenerator

# Initialize
db = Database()
db.seed_default_data()

# Run research
session = ResearchSession(db)
results = session.research_sector("Industrial Robotics")

# Generate report
generator = ReportGenerator(db)
report = generator.generate_sector_report("Industrial Robotics")
```

### AI Analysis
The system uses Ollama with qwen2.5:32b for:
- Extracting structured data from web search results
- Analyzing market trends
- Summarizing company information
- Processing interview transcripts

All AI outputs are forced to structured JSON format, not prose.

## Best Practices

1. **Always validate data**: Use the validation workflow to ensure data quality
2. **Track sources**: Every data point should have a source
3. **Use confidence levels**: Mark data confidence as high/medium/low/unverified
4. **Review changes**: Check monthly change reports for significant shifts
5. **Export regularly**: Keep JSON exports for backup and analysis
