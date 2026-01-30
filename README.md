# Robotics Intelligence Database

A structured database system for tracking robotics industry intelligence, with AI-powered research, change detection, and validation workflows.

## Features

- **Automated Research**: Web research via Brave Search API
- **AI Analysis**: Local Ollama integration for structured data extraction
- **SQLite Database**: Persistent storage with full audit trail
- **Validation Workflow**: Data quality management pipeline
- **Change Detection**: Month-over-month and year-over-year tracking
- **JSON Export**: Structured reports for downstream consumption

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env` and add your Brave API key:

```bash
# .env
BRAVE_API_KEY=your_api_key_here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:32b
```

### 3. Start Ollama

```bash
ollama serve
ollama pull qwen2.5:32b
```

### 4. Initialize Database

```bash
python scripts/run_research.py init
```

### 5. Run Research

```bash
# Check prerequisites
python scripts/run_research.py check

# Research a sector
python scripts/run_research.py sector "Industrial Robotics"

# Research a company
python scripts/run_research.py company "Boston Dynamics"
```

### 6. Export Data

```bash
# Export full database
python scripts/export_json.py full

# Export sector report
python scripts/export_json.py sector "Industrial Robotics"
```

## Project Structure

```
robotics-intelligence-db/
├── data/
│   ├── exports/          # JSON export files
│   ├── raw/              # Raw data files
│   └── robotics.db       # SQLite database (created on init)
├── scripts/
│   ├── run_research.py   # Research CLI tool
│   └── export_json.py    # Export CLI tool
├── skills/
│   └── robotics-intelligence-skill.md
├── src/
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLite database operations
│   ├── search.py         # Brave Search integration
│   ├── ai_analysis.py    # Ollama AI analysis
│   ├── data_ingestion.py # Research session management
│   ├── change_detection.py
│   ├── validation_workflow.py
│   └── reporting.py      # Report generation
├── tests/
│   ├── test_database.py
│   └── test_validation.py
├── .env                  # Environment configuration
├── .gitignore
├── requirements.txt
└── README.md
```

## Database Schema

### Sectors
- Industrial Robotics
- Mobile Robotics
- Service Robotics
- Agricultural Robotics
- Logistics Robotics
- Construction Robotics

### Tracked Dimensions
| Dimension | Unit | Description |
|-----------|------|-------------|
| market_size | USD billions | Total addressable market |
| market_growth_rate | percent | YoY growth rate |
| unit_shipments | units | Number shipped |
| average_selling_price | USD | Average unit price |
| deployment_count | units | Installed base |
| roi_payback_period | months | Typical ROI payback |
| labor_productivity_gain | percent | Productivity improvement |
| adoption_rate | percent | Market penetration |
| funding_raised | USD millions | Investment funding |
| employee_count | employees | Workforce size |

## API Usage

```python
from src.database import Database
from src.data_ingestion import ResearchSession
from src.reporting import ReportGenerator, JSONExporter

# Initialize database
db = Database()
db.seed_default_data()

# Run research
session = ResearchSession(db)
results = session.research_sector("Mobile Robotics", year=2025)

# Add manual data point
db.add_data_point(
    dimension_name="market_size",
    value=45.2,
    sector_name="Mobile Robotics",
    year=2025,
    confidence="high",
    notes="From IFR World Robotics 2025"
)

# Generate report
generator = ReportGenerator(db)
report = generator.generate_sector_report("Mobile Robotics")

# Export to file
exporter = JSONExporter()
exporter.export_report(report, "mobile_robotics_report.json")
```

## Validation Workflow

Data points progress through validation states:

```
pending → in_review → validated
                   → rejected
                   → outdated
```

```python
from src.validation_workflow import ValidationWorkflow

workflow = ValidationWorkflow(db)

# Get pending items
pending = workflow.get_pending_items()

# Validate an item
workflow.validate_item(data_point_id, "analyst_name")

# Reject with reason
workflow.reject_item(data_point_id, "analyst_name", "Outdated source")
```

## Change Detection

Track data changes over time:

```python
from src.change_detection import ChangeReporter

reporter = ChangeReporter()

# Monthly changes
report = reporter.generate_monthly_report(2025, 1)

# Year-over-year changes
annual = reporter.generate_annual_report(2025)
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Output Format

All exports are structured JSON. Example:

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
    ]
  }
}
```

## Requirements

- Python 3.9+
- Ollama running locally with qwen2.5:32b model
- Brave Search API key

## License

MIT
