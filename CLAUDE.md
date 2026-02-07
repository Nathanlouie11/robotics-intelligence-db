# CLAUDE.md — Robotics Intelligence Database

## Project Overview

A Python-based market intelligence platform for the robotics industry. It combines automated web research (Brave Search API), local AI analysis (Ollama), and a SQLite database with a Streamlit dashboard for interactive exploration. No REST API — all interaction is through CLI scripts, a Python SDK, and the Streamlit UI.

## Quick Reference

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (41 tests, all should pass)
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Initialize database
python scripts/run_research.py init

# Run Streamlit dashboard (localhost:8501)
python -m streamlit run scripts/run_dashboard.py

# Run research for a sector
python scripts/run_research.py sector "Industrial Robotics"

# Export data
python scripts/export_json.py full
python scripts/export_csv.py
```

## Architecture

```
robotics-intelligence-db/
├── src/                        # Core library (8 modules)
│   ├── config.py               # Environment config, taxonomies, constants
│   ├── database.py             # SQLite CRUD, schema, seeding (central data access)
│   ├── search.py               # Brave Search API client with rate limiting
│   ├── ai_analysis.py          # Ollama LLM integration for structured extraction
│   ├── data_ingestion.py       # Research session orchestration
│   ├── validation_workflow.py  # Data quality pipeline (pending→validated/rejected)
│   ├── change_detection.py     # MoM/YoY change tracking and significance analysis
│   └── reporting.py            # Report generation, JSON/CSV export
├── scripts/                    # CLI tools and dashboard
│   ├── run_dashboard.py        # Streamlit dashboard (~3000 lines)
│   ├── run_research.py         # Research CLI (init, check, sector, company, etc.)
│   ├── export_json.py          # JSON export CLI
│   ├── export_csv.py           # CSV export CLI
│   ├── refresh_data.py         # Update funding, partnerships, pain points
│   ├── enrich_data.py          # Data enrichment operations
│   ├── enrich_sources_deep.py  # Source verification and enrichment
│   └── expand_schema.py        # Database schema extensions
├── tests/                      # pytest test suite
│   ├── test_database.py        # Database CRUD, schema, statistics (17 tests)
│   └── test_validation.py      # Validation rules, workflow states (24 tests)
├── data/
│   ├── robotics.db             # SQLite database (populated, ~515 data points)
│   ├── exports/                # Generated CSV/JSON exports
│   ├── reports/                # Generated markdown sector reports
│   └── raw/                    # Raw input data
├── docs/                       # Documentation
├── skills/                     # Claude AI skill definitions
├── .streamlit/config.toml      # Streamlit theme and server config
├── requirements.txt            # Python dependencies
├── streamlit_app.py            # Streamlit Cloud entry point
└── .env                        # Environment variables (not committed)
```

## Layered Architecture

The codebase follows a layered pattern:

1. **Config layer** (`src/config.py`): Environment variables, constants, taxonomies
2. **Data layer** (`src/database.py`): SQLite access via the `Database` class (repository pattern)
3. **Service layer** (`src/search.py`, `src/ai_analysis.py`, `src/data_ingestion.py`, `src/validation_workflow.py`, `src/change_detection.py`): Business logic
4. **Presentation layer** (`src/reporting.py`, `scripts/run_dashboard.py`): Reports and UI

All modules depend on `Database` as the central data access object. Never bypass it for direct SQL.

## Database Schema

**20 tables** in SQLite (`data/robotics.db`):

- **Core**: `sectors` (6), `subcategories`, `dimensions` (18), `data_points` (515+), `sources` (504+), `changes_log`
- **Intelligence**: `companies`, `funding_rounds`, `partnerships`, `interviews`, `case_studies`, `pain_points`, `adoption_signals`, `news_items`
- **Technology**: `technologies`, `technology_sectors`, `technology_data_points`
- **Tracking**: `research_sessions`, `data_refresh_log`

**Six sectors**: Industrial, Mobile, Service, Agricultural, Logistics, Construction Robotics

**Data point fields**: numeric/text/JSON value, year/quarter/month, confidence level (high/medium/low/unverified), validation status (pending/in_review/validated/rejected/outdated), audit timestamps

## Code Conventions

### Style
- **Python 3.9+** with type hints throughout (`typing`: Optional, Dict, List, Any, Tuple)
- **Google-style docstrings** with Args, Returns, Raises sections
- **PEP 8** naming: `snake_case` for functions/variables, `PascalCase` for classes
- No explicit linter or formatter configured — follow existing style

### Patterns
- **Dataclasses** for structured data (`@dataclass`)
- **Enums** for constants (validation states, change types)
- **Context managers** for resource management
- **Row factory** for SQLite tuple→dict conversion
- **Foreign keys** with referential integrity enabled
- **JSON columns** for flexible metadata storage
- **Audit timestamps** (`created_at`, `updated_at`) on all records

### Testing
- **pytest** with fixtures for temporary databases
- Each test gets an isolated temp SQLite DB (`tempfile.mkstemp`) that is cleaned up after
- Tests import via `sys.path.insert` — the project has no `setup.py`/`pyproject.toml`
- Test classes grouped by concern: `TestDatabase`, `TestDataPointValues`, `TestValidationRules`, `TestValidationWorkflow`
- Run with: `pytest tests/ -v`

### Error Handling
- Specific exception messages with context
- Logging via standard library `logging` module
- Graceful degradation when external services (Ollama, Brave) are unavailable

## Environment Variables

Configured in `.env` (loaded by `python-dotenv`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `BRAVE_API_KEY` | (none) | Web search API key (required for research) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:32b` | LLM model for analysis |
| `DATABASE_PATH` | `data/robotics.db` | SQLite database location |
| `EXPORT_PATH` | `data/exports` | Export output directory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Key Dependencies

- **requests** — HTTP client for Brave Search and Ollama APIs
- **streamlit** + **plotly** — Dashboard UI and charts
- **pandas** — Data manipulation for exports and dashboard
- **reportlab** + **kaleido** — PDF generation with embedded charts
- **python-dotenv** — Environment variable loading
- **jsonschema** — JSON validation
- **SQLite** — Built-in, no separate installation needed

## Working with the Codebase

### Adding a new data dimension
1. Add to `DEFAULT_DIMENSIONS` in `src/config.py`
2. Database schema auto-seeds dimensions on init via `Database.seed_default_data()`
3. Add validation rules in `src/validation_workflow.py` if the dimension has bounds

### Adding a new sector
1. Add to `DEFAULT_SECTORS` in `src/config.py` with name, description, subcategories
2. Re-seed or run `python scripts/run_research.py init`

### Running research
Requires both Brave API key and Ollama running locally:
```bash
python scripts/run_research.py check    # Verify prerequisites
python scripts/run_research.py sector "Mobile Robotics"
python scripts/run_research.py company "Boston Dynamics"
python scripts/run_research.py technology "Computer Vision"
```

### Modifying the dashboard
The dashboard is a single large file at `scripts/run_dashboard.py` (~3000 lines). It uses Streamlit's page-based navigation with sections for Dashboard, Data Explorer, AI Query, Companies, Market Signals, Validation, and Import Data.

### Data validation workflow
```
pending → in_review → validated
                    → rejected
                    → outdated
```
Managed by `ValidationWorkflow` class. Rules are static methods on `ValidationRules` (source check, year check, value bounds, confidence validation).

## Deployment

- **Local**: `python -m streamlit run scripts/run_dashboard.py` (full features)
- **Streamlit Cloud**: Deploy with main file `scripts/run_dashboard.py` (no AI features — Ollama unavailable)

## Things to Watch Out For

- The database file `data/robotics.db` is committed and contains real data — avoid overwriting it carelessly
- No formal CI/CD pipeline exists — run `pytest tests/ -v` locally before committing
- The `.env` file may contain API keys — it's in `.gitignore`, never commit it
- Tests require `python-dotenv` installed (it's in requirements.txt but easy to miss in fresh environments)
- Scripts use `sys.path.insert` for imports rather than package installation — keep this pattern when adding new test files
