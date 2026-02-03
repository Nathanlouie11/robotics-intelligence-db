"""
Expand database schema for comprehensive robotics industry tracking.

New capabilities:
- Company profiles with funding history
- Partnership announcements
- Case studies and deployments
- Industry pain points
- Adoption signals
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DATABASE_PATH = Path(__file__).parent.parent / "data" / "robotics.db"

def get_connection():
    return sqlite3.connect(DATABASE_PATH)

def create_expanded_schema():
    """Create new tables for expanded tracking."""
    conn = get_connection()
    cursor = conn.cursor()

    print("Creating expanded schema...")

    # 1. COMPANIES TABLE - Central company registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            legal_name TEXT,
            founded_year INTEGER,
            hq_country TEXT,
            hq_city TEXT,
            employee_count INTEGER,
            employee_count_year INTEGER,
            website TEXT,
            linkedin_url TEXT,
            crunchbase_url TEXT,
            description TEXT,
            company_type TEXT CHECK(company_type IN ('startup', 'enterprise', 'public', 'subsidiary', 'research', 'government')),
            primary_sector_id INTEGER,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'acquired', 'defunct', 'ipo')),
            total_funding_millions REAL,
            last_valuation_millions REAL,
            last_valuation_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (primary_sector_id) REFERENCES sectors(id)
        )
    """)
    print("  [OK] companies table")

    # 2. FUNDING_ROUNDS TABLE - Track all funding events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funding_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            round_type TEXT CHECK(round_type IN ('seed', 'series_a', 'series_b', 'series_c', 'series_d', 'series_e', 'series_f', 'growth', 'debt', 'grant', 'ipo', 'acquisition', 'unknown')),
            amount_millions REAL,
            currency TEXT DEFAULT 'USD',
            announced_date TEXT,
            closed_date TEXT,
            lead_investors TEXT,  -- JSON array
            all_investors TEXT,   -- JSON array
            pre_money_valuation_millions REAL,
            post_money_valuation_millions REAL,
            source_id INTEGER,
            source_url TEXT,
            notes TEXT,
            confidence TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    """)
    print("  [OK] funding_rounds table")

    # 3. PARTNERSHIPS TABLE - Track strategic partnerships
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS partnerships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company1_id INTEGER NOT NULL,
            company2_id INTEGER,
            company2_name TEXT,  -- For companies not in our DB
            partnership_type TEXT CHECK(partnership_type IN ('integration', 'distribution', 'manufacturing', 'research', 'investment', 'acquisition', 'joint_venture', 'customer', 'supplier', 'other')),
            announcement_date TEXT,
            title TEXT,
            description TEXT,
            deal_value_millions REAL,
            duration_years REAL,
            sector_id INTEGER,
            source_id INTEGER,
            source_url TEXT,
            impact_assessment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company1_id) REFERENCES companies(id),
            FOREIGN KEY (company2_id) REFERENCES companies(id),
            FOREIGN KEY (sector_id) REFERENCES sectors(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    """)
    print("  [OK] partnerships table")

    # 4. CASE_STUDIES TABLE - Track real-world deployments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            customer_name TEXT,
            customer_industry TEXT,
            customer_size TEXT CHECK(customer_size IN ('smb', 'mid_market', 'enterprise', 'government', 'unknown')),
            deployment_year INTEGER,
            deployment_scale TEXT,  -- e.g., "50 robots across 3 warehouses"
            use_case TEXT,
            sector_id INTEGER,
            subcategory_id INTEGER,

            -- Quantified outcomes
            roi_percent REAL,
            payback_months REAL,
            productivity_gain_percent REAL,
            cost_reduction_percent REAL,
            labor_hours_saved REAL,
            units_deployed INTEGER,

            -- Qualitative outcomes
            outcomes_summary TEXT,
            challenges_faced TEXT,
            lessons_learned TEXT,

            source_id INTEGER,
            source_url TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (sector_id) REFERENCES sectors(id),
            FOREIGN KEY (subcategory_id) REFERENCES subcategories(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    """)
    print("  [OK] case_studies table")

    # 5. PAIN_POINTS TABLE - Track industry challenges
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pain_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_id INTEGER,
            category TEXT CHECK(category IN ('technical', 'cost', 'integration', 'workforce', 'regulatory', 'safety', 'scalability', 'reliability', 'other')),
            scale TEXT CHECK(scale IN ('startup', 'smb', 'mid_market', 'enterprise', 'industry_wide')),
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT CHECK(severity IN ('critical', 'high', 'medium', 'low')),
            frequency_mentioned INTEGER DEFAULT 1,  -- How often this comes up
            potential_solutions TEXT,
            companies_addressing TEXT,  -- JSON array of company IDs
            estimated_market_size_millions REAL,
            source_id INTEGER,
            first_identified_date TEXT,
            last_mentioned_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sector_id) REFERENCES sectors(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    """)
    print("  [OK] pain_points table")

    # 6. ADOPTION_SIGNALS TABLE - Track industry adoption trends
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adoption_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_id INTEGER,
            signal_type TEXT CHECK(signal_type IN ('deployment', 'pilot', 'rfi_rfp', 'hiring', 'budget_allocation', 'regulatory_approval', 'standard_adoption', 'market_entry', 'expansion', 'other')),
            title TEXT NOT NULL,
            description TEXT,
            company_id INTEGER,
            company_name TEXT,  -- For companies not in DB
            region TEXT,
            industry_vertical TEXT,
            signal_date TEXT,
            scale_indicator TEXT,  -- e.g., "Fortune 500", "10+ locations"
            source_id INTEGER,
            source_url TEXT,
            sentiment TEXT CHECK(sentiment IN ('positive', 'neutral', 'negative')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sector_id) REFERENCES sectors(id),
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    """)
    print("  [OK] adoption_signals table")

    # 7. NEWS_ITEMS TABLE - Track news for future processing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE,
            published_date TEXT,
            source_name TEXT,
            content_snippet TEXT,
            full_content TEXT,
            categories TEXT,  -- JSON array
            companies_mentioned TEXT,  -- JSON array
            sectors_mentioned TEXT,  -- JSON array
            sentiment TEXT,
            relevance_score REAL,
            is_processed INTEGER DEFAULT 0,
            processing_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  [OK] news_items table")

    # 8. DATA_REFRESH_LOG TABLE - Track refresh history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_refresh_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            refresh_type TEXT CHECK(refresh_type IN ('funding', 'partnerships', 'case_studies', 'pain_points', 'adoption', 'news', 'full')),
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            records_added INTEGER DEFAULT 0,
            records_updated INTEGER DEFAULT 0,
            errors TEXT,
            source TEXT,
            status TEXT CHECK(status IN ('running', 'completed', 'failed'))
        )
    """)
    print("  [OK] data_refresh_log table")

    # Create indexes for performance
    print("\nCreating indexes...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)",
        "CREATE INDEX IF NOT EXISTS idx_companies_type ON companies(company_type)",
        "CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(primary_sector_id)",
        "CREATE INDEX IF NOT EXISTS idx_funding_company ON funding_rounds(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_funding_date ON funding_rounds(announced_date)",
        "CREATE INDEX IF NOT EXISTS idx_partnerships_companies ON partnerships(company1_id, company2_id)",
        "CREATE INDEX IF NOT EXISTS idx_partnerships_date ON partnerships(announcement_date)",
        "CREATE INDEX IF NOT EXISTS idx_case_studies_company ON case_studies(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_case_studies_sector ON case_studies(sector_id)",
        "CREATE INDEX IF NOT EXISTS idx_pain_points_sector ON pain_points(sector_id)",
        "CREATE INDEX IF NOT EXISTS idx_pain_points_category ON pain_points(category)",
        "CREATE INDEX IF NOT EXISTS idx_adoption_sector ON adoption_signals(sector_id)",
        "CREATE INDEX IF NOT EXISTS idx_adoption_date ON adoption_signals(signal_date)",
        "CREATE INDEX IF NOT EXISTS idx_news_date ON news_items(published_date)",
        "CREATE INDEX IF NOT EXISTS idx_news_processed ON news_items(is_processed)",
    ]

    for idx in indexes:
        cursor.execute(idx)
    print("  [OK] All indexes created")

    conn.commit()
    conn.close()
    print("\nSchema expansion complete!")

def migrate_existing_funding_data():
    """Migrate existing funding data to new schema."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\nMigrating existing funding data...")

    # Get existing funding data points
    cursor.execute("""
        SELECT dp.id, dp.value, dp.value_text, dp.year, dp.notes, src.name, src.id
        FROM data_points dp
        JOIN dimensions dim ON dp.dimension_id = dim.id
        JOIN sources src ON dp.source_id = src.id
        WHERE dim.name = 'funding_raised'
    """)

    funding_data = cursor.fetchall()
    migrated = 0

    for row in funding_data:
        dp_id, amount, value_text, year, notes, source_name, source_id = row

        # Extract company name from source
        if '[STARTUP]' in source_name:
            company_name = source_name.replace('[STARTUP] ', '').split(' funding')[0].split(' raises')[0].split(' Raises')[0].split(' -')[0].strip()
        elif source_name.startswith('[') and ']' in source_name:
            company_name = source_name[1:source_name.index(']')].strip()
        else:
            company_name = source_name.split(' ')[0].strip()

        # Clean company name
        company_name = company_name.replace("'s", "").replace("'", "").strip()
        if len(company_name) < 2:
            continue

        # Check if company exists
        cursor.execute("SELECT id FROM companies WHERE name = ?", (company_name,))
        result = cursor.fetchone()

        if result:
            company_id = result[0]
        else:
            # Create company
            cursor.execute("""
                INSERT INTO companies (name, company_type, status)
                VALUES (?, 'startup', 'active')
            """, (company_name,))
            company_id = cursor.lastrowid

        # Determine round type from value_text
        round_type = 'unknown'
        if value_text:
            vt_lower = value_text.lower()
            if 'seed' in vt_lower:
                round_type = 'seed'
            elif 'series a' in vt_lower:
                round_type = 'series_a'
            elif 'series b' in vt_lower:
                round_type = 'series_b'
            elif 'series c' in vt_lower:
                round_type = 'series_c'
            elif 'series d' in vt_lower:
                round_type = 'series_d'
            elif 'series e' in vt_lower:
                round_type = 'series_e'
            elif 'series f' in vt_lower:
                round_type = 'series_f'

        # Check if funding round already exists
        cursor.execute("""
            SELECT id FROM funding_rounds
            WHERE company_id = ? AND amount_millions = ? AND round_type = ?
        """, (company_id, amount, round_type))

        if not cursor.fetchone():
            # Insert funding round
            cursor.execute("""
                INSERT INTO funding_rounds (company_id, round_type, amount_millions, announced_date, source_id, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (company_id, round_type, amount, f"{int(year)}-01-01" if year else None, source_id, notes))
            migrated += 1

    # Update company total funding
    cursor.execute("""
        UPDATE companies SET total_funding_millions = (
            SELECT SUM(amount_millions) FROM funding_rounds WHERE funding_rounds.company_id = companies.id
        )
    """)

    conn.commit()
    conn.close()
    print(f"  [OK] Migrated {migrated} funding rounds")
    print(f"  [OK] Created/updated company records")

def show_schema_summary():
    """Show summary of expanded schema."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("EXPANDED SCHEMA SUMMARY")
    print("="*60)

    tables = [
        ('companies', 'Company profiles'),
        ('funding_rounds', 'Funding events'),
        ('partnerships', 'Strategic partnerships'),
        ('case_studies', 'Real-world deployments'),
        ('pain_points', 'Industry challenges'),
        ('adoption_signals', 'Adoption trends'),
        ('news_items', 'News tracking'),
        ('data_refresh_log', 'Refresh history'),
    ]

    for table, desc in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:20} | {count:>6} records | {desc}")

    conn.close()

def main():
    print("="*60)
    print("ROBOTICS INTELLIGENCE - SCHEMA EXPANSION")
    print("="*60)

    create_expanded_schema()
    migrate_existing_funding_data()
    show_schema_summary()

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("""
1. Run data refresh script to populate new tables:
   python scripts/refresh_data.py --funding
   python scripts/refresh_data.py --partnerships
   python scripts/refresh_data.py --news

2. View data in dashboard:
   - New "Companies" page
   - New "Market Signals" page
   - Enhanced funding analysis

3. Set up scheduled refreshes:
   - Daily: News items
   - Weekly: Funding rounds, partnerships
   - Monthly: Case studies, pain points
""")

if __name__ == "__main__":
    main()
