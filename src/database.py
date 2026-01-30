"""
Database module for Robotics Intelligence Database.

Provides SQLite database management with full schema for tracking
robotics industry data points, sources, changes, and validation status.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

from .config import DATABASE_PATH, DEFAULT_SECTORS, DEFAULT_DIMENSIONS, DEFAULT_TECHNOLOGIES


class Database:
    """SQLite database manager for robotics intelligence data."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to config value.
        """
        self.db_path = db_path or DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Sectors table - top-level categories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Subcategories table - nested under sectors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subcategories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sector_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id),
                    UNIQUE(sector_id, name)
                )
            """)

            # Dimensions table - what metrics we track
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dimensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    unit TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sources table - where data comes from
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT,
                    source_type TEXT,  -- 'research_report', 'news', 'company', 'interview', 'government'
                    reliability_score REAL DEFAULT 0.5,  -- 0.0 to 1.0
                    last_accessed TIMESTAMP,
                    metadata TEXT,  -- JSON blob for extra data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Data points table - the actual intelligence data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sector_id INTEGER,
                    subcategory_id INTEGER,
                    dimension_id INTEGER NOT NULL,
                    value REAL,
                    value_text TEXT,  -- For non-numeric values
                    value_json TEXT,  -- For complex structured data
                    year INTEGER,
                    quarter INTEGER,  -- 1-4, NULL if annual
                    month INTEGER,    -- 1-12, NULL if not monthly
                    source_id INTEGER,
                    confidence TEXT DEFAULT 'medium',  -- high, medium, low, unverified
                    validation_status TEXT DEFAULT 'pending',  -- pending, in_review, validated, rejected, outdated
                    validated_by TEXT,
                    validated_at TIMESTAMP,
                    notes TEXT,
                    metadata TEXT,  -- JSON blob
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sector_id) REFERENCES sectors(id),
                    FOREIGN KEY (subcategory_id) REFERENCES subcategories(id),
                    FOREIGN KEY (dimension_id) REFERENCES dimensions(id),
                    FOREIGN KEY (source_id) REFERENCES sources(id)
                )
            """)

            # Changes log table - track all modifications
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS changes_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,  -- 'insert', 'update', 'delete'
                    old_value TEXT,  -- JSON of previous state
                    new_value TEXT,  -- JSON of new state
                    changed_by TEXT,
                    change_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Interviews table - expert interview tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expert_name TEXT NOT NULL,
                    expert_title TEXT,
                    expert_company TEXT,
                    interview_date DATE,
                    topics TEXT,  -- JSON array of topics
                    key_insights TEXT,  -- JSON array of insights
                    transcript_path TEXT,
                    summary TEXT,
                    follow_up_needed BOOLEAN DEFAULT FALSE,
                    validation_status TEXT DEFAULT 'pending',
                    metadata TEXT,  -- JSON blob
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Technologies table - cross-cutting technologies
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technologies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,  -- 'perception', 'navigation', 'manipulation', 'ai_software', 'safety', 'connectivity', 'power'
                    description TEXT,
                    maturity_level TEXT,  -- 'emerging', 'growing', 'mature'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Technology-Sector mapping (many-to-many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technology_sectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    technology_id INTEGER NOT NULL,
                    sector_id INTEGER NOT NULL,
                    relevance TEXT,  -- 'high', 'medium', 'low'
                    notes TEXT,
                    FOREIGN KEY (technology_id) REFERENCES technologies(id),
                    FOREIGN KEY (sector_id) REFERENCES sectors(id),
                    UNIQUE(technology_id, sector_id)
                )
            """)

            # Technology data points - extends data_points concept
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS technology_data_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    technology_id INTEGER NOT NULL,
                    dimension_id INTEGER NOT NULL,
                    value REAL,
                    value_text TEXT,
                    value_json TEXT,
                    year INTEGER,
                    source_id INTEGER,
                    confidence TEXT DEFAULT 'medium',
                    validation_status TEXT DEFAULT 'pending',
                    notes TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (technology_id) REFERENCES technologies(id),
                    FOREIGN KEY (dimension_id) REFERENCES dimensions(id),
                    FOREIGN KEY (source_id) REFERENCES sources(id)
                )
            """)

            # Research sessions table - track research runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type TEXT NOT NULL,  -- 'sector_deep_dive', 'company_research', 'trend_analysis'
                    target TEXT NOT NULL,  -- What was researched
                    queries_run INTEGER DEFAULT 0,
                    sources_found INTEGER DEFAULT 0,
                    data_points_created INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',  -- running, completed, failed
                    error_message TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_points_sector ON data_points(sector_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_points_dimension ON data_points(dimension_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_points_year ON data_points(year)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_points_validation ON data_points(validation_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_changes_log_table ON changes_log(table_name, record_id)")

            conn.commit()

    def seed_default_data(self) -> Dict[str, int]:
        """
        Seed database with default sectors and dimensions.

        Returns:
            dict: Counts of records created
        """
        sectors_created = 0
        subcategories_created = 0
        dimensions_created = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert default sectors and subcategories
            for sector_data in DEFAULT_SECTORS:
                cursor.execute(
                    "INSERT OR IGNORE INTO sectors (name, description) VALUES (?, ?)",
                    (sector_data["name"], sector_data["description"])
                )
                if cursor.rowcount > 0:
                    sectors_created += 1

                # Get sector ID
                cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_data["name"],))
                sector_id = cursor.fetchone()[0]

                # Insert subcategories
                for subcat_name in sector_data.get("subcategories", []):
                    cursor.execute(
                        "INSERT OR IGNORE INTO subcategories (sector_id, name) VALUES (?, ?)",
                        (sector_id, subcat_name)
                    )
                    if cursor.rowcount > 0:
                        subcategories_created += 1

            # Insert default dimensions
            for dim_data in DEFAULT_DIMENSIONS:
                cursor.execute(
                    "INSERT OR IGNORE INTO dimensions (name, unit, description) VALUES (?, ?, ?)",
                    (dim_data["name"], dim_data["unit"], dim_data["description"])
                )
                if cursor.rowcount > 0:
                    dimensions_created += 1

            # Insert default technologies
            technologies_created = 0
            for tech_data in DEFAULT_TECHNOLOGIES:
                cursor.execute(
                    "INSERT OR IGNORE INTO technologies (name, category, description, maturity_level) VALUES (?, ?, ?, ?)",
                    (tech_data["name"], tech_data["category"], tech_data["description"], tech_data["maturity"])
                )
                if cursor.rowcount > 0:
                    technologies_created += 1

            conn.commit()

        return {
            "sectors_created": sectors_created,
            "subcategories_created": subcategories_created,
            "dimensions_created": dimensions_created,
            "technologies_created": technologies_created
        }

    # ==================== SECTOR OPERATIONS ====================

    def get_sectors(self) -> List[Dict[str, Any]]:
        """Get all sectors with their subcategories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sectors ORDER BY name")
            sectors = [dict(row) for row in cursor.fetchall()]

            for sector in sectors:
                cursor.execute(
                    "SELECT * FROM subcategories WHERE sector_id = ? ORDER BY name",
                    (sector["id"],)
                )
                sector["subcategories"] = [dict(row) for row in cursor.fetchall()]

            return sectors

    def get_sector_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a sector by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sectors WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== DIMENSION OPERATIONS ====================

    def get_dimensions(self) -> List[Dict[str, Any]]:
        """Get all dimensions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dimensions ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def get_dimension_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a dimension by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dimensions WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== SOURCE OPERATIONS ====================

    def add_source(self, name: str, url: Optional[str] = None,
                   source_type: str = "news", reliability_score: float = 0.5,
                   metadata: Optional[Dict] = None) -> int:
        """
        Add a new source.

        Returns:
            int: ID of created source
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sources (name, url, source_type, reliability_score, last_accessed, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, url, source_type, reliability_score,
                  datetime.now().isoformat(), json.dumps(metadata) if metadata else None))
            return cursor.lastrowid

    def get_or_create_source(self, name: str, url: Optional[str] = None, **kwargs) -> int:
        """Get existing source by URL or create new one."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if url:
                cursor.execute("SELECT id FROM sources WHERE url = ?", (url,))
                row = cursor.fetchone()
                if row:
                    return row[0]
            return self.add_source(name, url, **kwargs)

    # ==================== DATA POINT OPERATIONS ====================

    def add_data_point(self, dimension_name: str, value: Any,
                       sector_name: Optional[str] = None,
                       subcategory_name: Optional[str] = None,
                       year: Optional[int] = None,
                       quarter: Optional[int] = None,
                       month: Optional[int] = None,
                       source_id: Optional[int] = None,
                       confidence: str = "medium",
                       notes: Optional[str] = None,
                       metadata: Optional[Dict] = None) -> int:
        """
        Add a new data point.

        Args:
            dimension_name: Name of the dimension (e.g., 'market_size')
            value: The data value (numeric, string, or dict)
            sector_name: Optional sector name
            subcategory_name: Optional subcategory name
            year: Data year
            quarter: Optional quarter (1-4)
            month: Optional month (1-12)
            source_id: ID of source
            confidence: Confidence level
            notes: Additional notes
            metadata: Extra metadata as dict

        Returns:
            int: ID of created data point
        """
        # Resolve IDs
        dimension = self.get_dimension_by_name(dimension_name)
        if not dimension:
            raise ValueError(f"Unknown dimension: {dimension_name}")
        dimension_id = dimension["id"]

        sector_id = None
        subcategory_id = None

        if sector_name:
            sector = self.get_sector_by_name(sector_name)
            if sector:
                sector_id = sector["id"]

                if subcategory_name:
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM subcategories WHERE sector_id = ? AND name = ?",
                            (sector_id, subcategory_name)
                        )
                        row = cursor.fetchone()
                        if row:
                            subcategory_id = row[0]

        # Determine value storage
        value_numeric = None
        value_text = None
        value_json = None

        if isinstance(value, (int, float)):
            value_numeric = float(value)
        elif isinstance(value, dict):
            value_json = json.dumps(value)
        else:
            value_text = str(value)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO data_points
                (sector_id, subcategory_id, dimension_id, value, value_text, value_json,
                 year, quarter, month, source_id, confidence, notes, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sector_id, subcategory_id, dimension_id, value_numeric, value_text, value_json,
                  year, quarter, month, source_id, confidence, notes,
                  json.dumps(metadata) if metadata else None))

            data_point_id = cursor.lastrowid

            # Log the change
            self._log_change(cursor, "data_points", data_point_id, "insert", None, {
                "dimension": dimension_name,
                "value": value,
                "sector": sector_name,
                "year": year
            })

            return data_point_id

    def get_data_points(self,
                        sector_name: Optional[str] = None,
                        dimension_name: Optional[str] = None,
                        year: Optional[int] = None,
                        validation_status: Optional[str] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query data points with filters.

        Returns:
            list: List of data point dictionaries
        """
        query = """
            SELECT dp.*,
                   s.name as sector_name,
                   sc.name as subcategory_name,
                   d.name as dimension_name,
                   d.unit as dimension_unit,
                   src.name as source_name,
                   src.url as source_url
            FROM data_points dp
            LEFT JOIN sectors s ON dp.sector_id = s.id
            LEFT JOIN subcategories sc ON dp.subcategory_id = sc.id
            LEFT JOIN dimensions d ON dp.dimension_id = d.id
            LEFT JOIN sources src ON dp.source_id = src.id
            WHERE 1=1
        """
        params = []

        if sector_name:
            query += " AND s.name = ?"
            params.append(sector_name)

        if dimension_name:
            query += " AND d.name = ?"
            params.append(dimension_name)

        if year:
            query += " AND dp.year = ?"
            params.append(year)

        if validation_status:
            query += " AND dp.validation_status = ?"
            params.append(validation_status)

        query += " ORDER BY dp.created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # Parse JSON fields
                if data.get("value_json"):
                    data["value_structured"] = json.loads(data["value_json"])
                if data.get("metadata"):
                    data["metadata"] = json.loads(data["metadata"])
                results.append(data)
            return results

    def update_data_point_validation(self, data_point_id: int,
                                     status: str, validated_by: str,
                                     notes: Optional[str] = None) -> bool:
        """Update validation status of a data point."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get current state for change log
            cursor.execute("SELECT * FROM data_points WHERE id = ?", (data_point_id,))
            old_row = cursor.fetchone()
            if not old_row:
                return False
            old_data = dict(old_row)

            cursor.execute("""
                UPDATE data_points
                SET validation_status = ?, validated_by = ?, validated_at = ?,
                    notes = COALESCE(?, notes), updated_at = ?
                WHERE id = ?
            """, (status, validated_by, datetime.now().isoformat(),
                  notes, datetime.now().isoformat(), data_point_id))

            # Log the change
            self._log_change(cursor, "data_points", data_point_id, "update",
                            {"validation_status": old_data["validation_status"]},
                            {"validation_status": status, "validated_by": validated_by})

            return cursor.rowcount > 0

    # ==================== CHANGE TRACKING ====================

    def _log_change(self, cursor, table_name: str, record_id: int,
                    change_type: str, old_value: Any, new_value: Any,
                    changed_by: str = "system", reason: str = None):
        """Log a change to the changes_log table."""
        cursor.execute("""
            INSERT INTO changes_log (table_name, record_id, change_type,
                                     old_value, new_value, changed_by, change_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (table_name, record_id, change_type,
              json.dumps(old_value) if old_value else None,
              json.dumps(new_value) if new_value else None,
              changed_by, reason))

    def get_changes(self, table_name: Optional[str] = None,
                    since: Optional[datetime] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get change history."""
        query = "SELECT * FROM changes_log WHERE 1=1"
        params = []

        if table_name:
            query += " AND table_name = ?"
            params.append(table_name)

        if since:
            query += " AND created_at >= ?"
            params.append(since.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get("old_value"):
                    data["old_value"] = json.loads(data["old_value"])
                if data.get("new_value"):
                    data["new_value"] = json.loads(data["new_value"])
                results.append(data)
            return results

    # ==================== TECHNOLOGY OPERATIONS ====================

    def get_technologies(self, category: str = None) -> List[Dict[str, Any]]:
        """Get all technologies, optionally filtered by category."""
        query = "SELECT * FROM technologies"
        params = []

        if category:
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY category, name"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_technology_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a technology by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM technologies WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_technology(self, name: str, category: str, description: str = None,
                       maturity_level: str = "growing") -> int:
        """Add a new technology."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO technologies (name, category, description, maturity_level)
                VALUES (?, ?, ?, ?)
            """, (name, category, description, maturity_level))
            return cursor.lastrowid

    def link_technology_to_sector(self, technology_name: str, sector_name: str,
                                   relevance: str = "high", notes: str = None):
        """Link a technology to a sector."""
        tech = self.get_technology_by_name(technology_name)
        sector = self.get_sector_by_name(sector_name)

        if not tech or not sector:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO technology_sectors (technology_id, sector_id, relevance, notes)
                VALUES (?, ?, ?, ?)
            """, (tech["id"], sector["id"], relevance, notes))
            return True

    def add_technology_data_point(self, technology_name: str, dimension_name: str,
                                   value: Any, year: int = None,
                                   source_id: int = None, confidence: str = "medium",
                                   notes: str = None, metadata: Dict = None) -> int:
        """Add a data point for a technology."""
        tech = self.get_technology_by_name(technology_name)
        dim = self.get_dimension_by_name(dimension_name)

        if not tech:
            raise ValueError(f"Unknown technology: {technology_name}")
        if not dim:
            raise ValueError(f"Unknown dimension: {dimension_name}")

        # Determine value storage
        value_numeric = None
        value_text = None
        value_json = None

        if isinstance(value, (int, float)):
            value_numeric = float(value)
        elif isinstance(value, dict):
            value_json = json.dumps(value)
        else:
            value_text = str(value)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO technology_data_points
                (technology_id, dimension_id, value, value_text, value_json,
                 year, source_id, confidence, notes, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tech["id"], dim["id"], value_numeric, value_text, value_json,
                  year, source_id, confidence, notes,
                  json.dumps(metadata) if metadata else None))
            return cursor.lastrowid

    def get_technology_data_points(self, technology_name: str = None,
                                    dimension_name: str = None,
                                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get technology data points with filters."""
        query = """
            SELECT tdp.*,
                   t.name as technology_name,
                   t.category as technology_category,
                   d.name as dimension_name,
                   d.unit as dimension_unit,
                   src.name as source_name,
                   src.url as source_url
            FROM technology_data_points tdp
            LEFT JOIN technologies t ON tdp.technology_id = t.id
            LEFT JOIN dimensions d ON tdp.dimension_id = d.id
            LEFT JOIN sources src ON tdp.source_id = src.id
            WHERE 1=1
        """
        params = []

        if technology_name:
            query += " AND t.name = ?"
            params.append(technology_name)

        if dimension_name:
            query += " AND d.name = ?"
            params.append(dimension_name)

        query += " ORDER BY tdp.created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get("value_json"):
                    data["value_structured"] = json.loads(data["value_json"])
                if data.get("metadata"):
                    data["metadata"] = json.loads(data["metadata"])
                results.append(data)
            return results

    # ==================== INTERVIEW OPERATIONS ====================

    def add_interview(self, expert_name: str, expert_title: str = None,
                      expert_company: str = None, interview_date: str = None,
                      topics: List[str] = None, key_insights: List[str] = None,
                      summary: str = None, metadata: Dict = None) -> int:
        """Add an interview record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interviews
                (expert_name, expert_title, expert_company, interview_date,
                 topics, key_insights, summary, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (expert_name, expert_title, expert_company, interview_date,
                  json.dumps(topics) if topics else None,
                  json.dumps(key_insights) if key_insights else None,
                  summary, json.dumps(metadata) if metadata else None))
            return cursor.lastrowid

    def get_interviews(self, validation_status: str = None) -> List[Dict[str, Any]]:
        """Get interview records."""
        query = "SELECT * FROM interviews"
        params = []

        if validation_status:
            query += " WHERE validation_status = ?"
            params.append(validation_status)

        query += " ORDER BY interview_date DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get("topics"):
                    data["topics"] = json.loads(data["topics"])
                if data.get("key_insights"):
                    data["key_insights"] = json.loads(data["key_insights"])
                if data.get("metadata"):
                    data["metadata"] = json.loads(data["metadata"])
                results.append(data)
            return results

    # ==================== RESEARCH SESSION TRACKING ====================

    def start_research_session(self, session_type: str, target: str) -> int:
        """Start tracking a research session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO research_sessions (session_type, target)
                VALUES (?, ?)
            """, (session_type, target))
            return cursor.lastrowid

    def update_research_session(self, session_id: int,
                                queries_run: int = None,
                                sources_found: int = None,
                                data_points_created: int = None,
                                status: str = None,
                                error_message: str = None):
        """Update research session progress."""
        updates = []
        params = []

        if queries_run is not None:
            updates.append("queries_run = ?")
            params.append(queries_run)
        if sources_found is not None:
            updates.append("sources_found = ?")
            params.append(sources_found)
        if data_points_created is not None:
            updates.append("data_points_created = ?")
            params.append(data_points_created)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status in ("completed", "failed"):
                updates.append("completed_at = ?")
                params.append(datetime.now().isoformat())
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if not updates:
            return

        params.append(session_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE research_sessions
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)

    # ==================== STATISTICS ====================

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Count records in each table
            for table in ["sectors", "subcategories", "dimensions", "sources",
                         "data_points", "interviews", "changes_log"]:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]

            # Validation status breakdown
            cursor.execute("""
                SELECT validation_status, COUNT(*)
                FROM data_points
                GROUP BY validation_status
            """)
            stats["validation_breakdown"] = dict(cursor.fetchall())

            # Data points by sector
            cursor.execute("""
                SELECT s.name, COUNT(dp.id)
                FROM sectors s
                LEFT JOIN data_points dp ON s.id = dp.sector_id
                GROUP BY s.id
            """)
            stats["data_points_by_sector"] = dict(cursor.fetchall())

            # Recent activity
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*)
                FROM data_points
                WHERE created_at >= DATE('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            stats["recent_activity"] = dict(cursor.fetchall())

            return stats


# Convenience function for quick database access
def get_db(db_path: Optional[str] = None) -> Database:
    """Get a database instance."""
    return Database(db_path)


if __name__ == "__main__":
    # Test database initialization
    db = Database()
    result = db.seed_default_data()
    print(f"Seeded database: {result}")

    stats = db.get_statistics()
    print(f"Statistics: {json.dumps(stats, indent=2)}")
