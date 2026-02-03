#!/usr/bin/env python3
"""
Streamlit Dashboard for Robotics Intelligence Database.

Run with: streamlit run scripts/run_dashboard.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import json
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.config import DATABASE_PATH, OLLAMA_HOST, OLLAMA_MODEL

# OpenRouter API Configuration (for cloud deployment)
def get_openrouter_key():
    """Get OpenRouter API key from various sources."""
    # 1. Check environment variable
    key = os.getenv('OPENROUTER_KEY')
    if key:
        return key
    # 2. Check Streamlit secrets
    try:
        if hasattr(st, 'secrets') and 'OPENROUTER_KEY' in st.secrets:
            return st.secrets['OPENROUTER_KEY']
    except Exception:
        pass
    # 3. Check session state (user input)
    if 'openrouter_key' in st.session_state and st.session_state.openrouter_key:
        return st.session_state.openrouter_key
    return None

OPENROUTER_MODEL = "google/gemini-2.0-flash-lite-001"

# Page configuration
st.set_page_config(
    page_title="Robotics Intelligence Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Database connection (no caching to ensure fresh data)
def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DATABASE_PATH, check_same_thread=False)


def run_query(query: str, params: tuple = ()) -> pd.DataFrame:
    """Run a SQL query and return results as DataFrame."""
    conn = get_db_connection()
    return pd.read_sql_query(query, conn, params=params)


def get_schema_info() -> str:
    """Get database schema information for LLM context."""
    schema = """
Database Schema:
- sectors: id, name, description
- subcategories: id, sector_id, name, description
- dimensions: id, name, unit, description
- sources: id, name, url, source_type, reliability_score
  * IMPORTANT: Company names are stored in sources.name
  * Format: "[STARTUP] Company Name..." or "[Company Name] Report Title..."
  * Example: "[STARTUP] Exotec raises $335 million..."
- data_points: id, sector_id, subcategory_id, dimension_id, value, value_text,
               year, quarter, month, source_id, confidence, validation_status, notes
  * value = numeric value (e.g., 335 for $335M)
  * value_text = text description (e.g., "$335M Series B")
- technologies: id, name, category, description, maturity_level
- technology_data_points: id, technology_id, dimension_id, value, value_text, year, confidence

Key dimensions (metrics tracked):
- market_size (USD billions)
- market_growth_rate (percent)
- unit_shipments (units)
- average_selling_price (USD)
- deployment_count (units)
- adoption_rate (percent)
- funding_raised (USD millions) - value is the amount, source.name contains company

Example query for top funded companies:
SELECT src.name as company_source, dp.value as funding_millions, dp.value_text, dp.year
FROM data_points dp
JOIN dimensions dim ON dp.dimension_id = dim.id
JOIN sources src ON dp.source_id = src.id
WHERE dim.name = 'funding_raised'
ORDER BY dp.value DESC LIMIT 10;

Confidence levels: high, medium, low, unverified
Validation status: pending, in_review, validated, rejected, outdated

Sectors: Industrial Robotics, Mobile Robotics, Service Robotics,
         Agricultural Robotics, Logistics Robotics, Construction Robotics
"""
    return schema


def query_ollama(prompt: str, context: str = "") -> str:
    """Query Ollama for natural language processing."""
    system_prompt = f"""You are a helpful assistant for a robotics intelligence database.
You help users query and understand data about the robotics industry.

{get_schema_info()}

When the user asks a question:
1. If they want data, generate a valid SQLite query
2. Wrap SQL queries in ```sql and ``` tags
3. Explain what the query does
4. If they ask for analysis, provide insights based on available data

{context}

Be concise and helpful."""

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": f"{system_prompt}\n\nUser question: {prompt}",
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2000}
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("response", "No response from model")
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama. Make sure it's running at " + OLLAMA_HOST
    except requests.exceptions.Timeout:
        return "Error: Request timed out. The model may be loading or overloaded."
    except Exception as e:
        return f"Error: {str(e)}"


def extract_sql_from_response(response: str) -> str:
    """Extract SQL query from LLM response."""
    import re
    # Look for SQL in code blocks
    sql_match = re.search(r'```sql\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match.group(1).strip()
    # Look for SELECT statements
    select_match = re.search(r'(SELECT\s+.*?;)', response, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()
    return ""


def check_ollama_status() -> bool:
    """Check if Ollama is available."""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_openrouter_status() -> bool:
    """Check if OpenRouter API key is available."""
    key = get_openrouter_key()
    return key is not None and len(key) > 10


def query_openrouter(prompt: str, context: str = "") -> str:
    """Query OpenRouter API for natural language processing."""
    system_prompt = f"""You are a helpful assistant for a robotics intelligence database.
You help users query and understand data about the robotics industry.

{get_schema_info()}

When the user asks a question:
1. If they want data, generate a valid SQLite query
2. Wrap SQL queries in ```sql and ``` tags
3. Explain what the query does
4. If they ask for analysis, provide insights based on available data

{context}

Be concise and helpful."""

    try:
        api_key = get_openrouter_key()
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://robotics-intelligence.streamlit.app"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.3
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        return "Error: Request timed out. Please try again."
    except Exception as e:
        return f"Error: {str(e)}"


def get_ai_backend() -> str:
    """Determine which AI backend is available."""
    if check_ollama_status():
        return "ollama"
    elif check_openrouter_status():
        return "openrouter"
    return None


# Sidebar
with st.sidebar:
    st.title("🤖 Robotics Intelligence")

    # Import Data button at top
    if st.button("📤 Import Data", use_container_width=True):
        st.session_state.current_page = "📤 Import Data"

    st.markdown("---")

    # Navigation
    nav_selection = st.radio(
        "Navigation",
        ["📊 Dashboard", "🏢 Companies", "📈 Market Signals", "🔍 Data Explorer", "📑 Technical Intelligence", "✅ Validation", "📋 Methodology", "💬 AI Query Interface"],
        label_visibility="collapsed"
    )

    # Handle page selection (button overrides radio)
    if 'current_page' in st.session_state and st.session_state.current_page == "📤 Import Data":
        page = "📤 Import Data"
    else:
        page = nav_selection
        st.session_state.current_page = nav_selection

    st.markdown("---")

    # AI Backend status
    ai_backend = get_ai_backend()
    if ai_backend == "ollama":
        st.success(f"✅ AI: Ollama")
        st.caption(f"Model: {OLLAMA_MODEL}")
    elif ai_backend == "openrouter":
        st.success(f"✅ AI: OpenRouter")
        st.caption(f"Model: Gemini Flash")
    else:
        st.warning("⚠️ AI Offline")
        st.caption("Configure OPENROUTER_KEY in secrets")

    st.markdown("---")
    st.caption(f"Database: {Path(DATABASE_PATH).name}")


# Main content based on selected page
if page == "📊 Dashboard":
    st.title("Robotics Intelligence Dashboard")

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    # Get counts
    data_points_count = run_query("SELECT COUNT(*) as count FROM data_points").iloc[0]['count']
    sectors_count = run_query("SELECT COUNT(*) as count FROM sectors").iloc[0]['count']
    sources_count = run_query("SELECT COUNT(*) as count FROM sources").iloc[0]['count']
    tech_count = run_query("SELECT COUNT(*) as count FROM technologies").iloc[0]['count']

    with col1:
        st.metric("📈 Data Points", f"{data_points_count:,}")
    with col2:
        st.metric("🏭 Sectors", sectors_count)
    with col3:
        st.metric("📚 Sources", sources_count)
    with col4:
        st.metric("⚙️ Technologies", tech_count)

    st.markdown("---")

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Growth Rates by Sector")

        # Get growth rate data
        growth_query = """
            SELECT s.name as sector,
                   dp.value as growth_rate,
                   dp.year,
                   dp.confidence
            FROM data_points dp
            JOIN sectors s ON dp.sector_id = s.id
            JOIN dimensions d ON dp.dimension_id = d.id
            WHERE d.name = 'market_growth_rate'
            AND dp.value IS NOT NULL
            ORDER BY dp.value DESC
        """
        growth_df = run_query(growth_query)

        if not growth_df.empty:
            # Aggregate by sector (average if multiple years)
            sector_growth = growth_df.groupby('sector')['growth_rate'].mean().reset_index()
            sector_growth = sector_growth.sort_values('growth_rate', ascending=True)

            fig = px.bar(
                sector_growth,
                x='growth_rate',
                y='sector',
                orientation='h',
                title='Average Growth Rate by Sector (%)',
                labels={'growth_rate': 'Growth Rate (%)', 'sector': 'Sector'},
                color='growth_rate',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No growth rate data available yet.")

    with col2:
        st.subheader("Market Size by Sector")

        # Get market size data
        market_query = """
            SELECT s.name as sector,
                   dp.value as market_size,
                   dp.year
            FROM data_points dp
            JOIN sectors s ON dp.sector_id = s.id
            JOIN dimensions d ON dp.dimension_id = d.id
            WHERE d.name = 'market_size'
            AND dp.value IS NOT NULL
            ORDER BY dp.value DESC
        """
        market_df = run_query(market_query)

        if not market_df.empty:
            # Get latest year for each sector
            latest_market = market_df.sort_values('year', ascending=False).groupby('sector').first().reset_index()

            fig = px.pie(
                latest_market,
                values='market_size',
                names='sector',
                title='Market Size Distribution (USD Billions)',
                hole=0.4
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No market size data available yet.")

    # Data quality metrics
    st.markdown("---")
    st.subheader("Data Quality Overview")

    col1, col2 = st.columns(2)

    with col1:
        # Validation status breakdown
        validation_query = """
            SELECT validation_status, COUNT(*) as count
            FROM data_points
            GROUP BY validation_status
        """
        validation_df = run_query(validation_query)

        if not validation_df.empty:
            fig = px.pie(
                validation_df,
                values='count',
                names='validation_status',
                title='Data Validation Status',
                color='validation_status',
                color_discrete_map={
                    'validated': '#28a745',
                    'pending': '#ffc107',
                    'in_review': '#17a2b8',
                    'rejected': '#dc3545',
                    'outdated': '#6c757d'
                }
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, width='stretch')

    with col2:
        # Confidence level breakdown
        confidence_query = """
            SELECT confidence, COUNT(*) as count
            FROM data_points
            GROUP BY confidence
        """
        confidence_df = run_query(confidence_query)

        if not confidence_df.empty:
            fig = px.bar(
                confidence_df,
                x='confidence',
                y='count',
                title='Data Points by Confidence Level',
                color='confidence',
                color_discrete_map={
                    'high': '#28a745',
                    'medium': '#ffc107',
                    'low': '#fd7e14',
                    'unverified': '#dc3545'
                }
            )
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, width='stretch')


elif page == "🏢 Companies":
    st.title("Company Profiles")
    st.markdown("Track robotics companies with funding history and status.")

    # Check if companies table exists
    try:
        companies_count = run_query("SELECT COUNT(*) as count FROM companies").iloc[0]['count']
    except:
        st.warning("Companies table not found. Run `python scripts/expand_schema.py` to create it.")
        st.stop()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🏢 Total Companies", companies_count)
    with col2:
        startup_count = run_query("SELECT COUNT(*) as count FROM companies WHERE company_type = 'startup'").iloc[0]['count']
        st.metric("🚀 Startups", startup_count)
    with col3:
        total_funding = run_query("SELECT SUM(total_funding_millions) as total FROM companies").iloc[0]['total'] or 0
        st.metric("💰 Total Funding", f"${total_funding:,.0f}M")
    with col4:
        funding_rounds = run_query("SELECT COUNT(*) as count FROM funding_rounds").iloc[0]['count']
        st.metric("📊 Funding Rounds", funding_rounds)

    st.markdown("---")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        company_type_filter = st.selectbox(
            "Company Type",
            ["All", "startup", "enterprise", "public", "research"],
            key="company_type"
        )

    with col2:
        status_filter = st.selectbox(
            "Status",
            ["All", "active", "acquired", "defunct", "ipo"],
            key="company_status"
        )

    with col3:
        search_term = st.text_input("Search Company Name", key="company_search")

    # Build query
    company_query = """
        SELECT
            c.id,
            c.name,
            c.company_type,
            c.status,
            c.founded_year,
            c.hq_country,
            c.employee_count,
            c.total_funding_millions,
            c.website,
            (SELECT COUNT(*) FROM funding_rounds WHERE company_id = c.id) as funding_rounds,
            (SELECT MAX(announced_date) FROM funding_rounds WHERE company_id = c.id) as last_funding
        FROM companies c
        WHERE 1=1
    """
    params = []

    if company_type_filter != "All":
        company_query += " AND c.company_type = ?"
        params.append(company_type_filter)

    if status_filter != "All":
        company_query += " AND c.status = ?"
        params.append(status_filter)

    if search_term:
        company_query += " AND c.name LIKE ?"
        params.append(f"%{search_term}%")

    company_query += " ORDER BY c.total_funding_millions DESC NULLS LAST LIMIT 100"

    companies_df = run_query(company_query, tuple(params))

    st.subheader(f"Companies ({len(companies_df)} results)")

    if not companies_df.empty:
        for idx, row in companies_df.iterrows():
            # Status badge
            status_emoji = {"active": "🟢", "acquired": "🔵", "defunct": "🔴", "ipo": "🟡"}.get(row['status'], "⚪")
            type_emoji = {"startup": "🚀", "enterprise": "🏢", "public": "📈", "research": "🔬"}.get(row['company_type'], "")

            funding_display = f"${row['total_funding_millions']:,.0f}M" if row['total_funding_millions'] else "N/A"

            with st.expander(f"{status_emoji} {type_emoji} **{row['name']}** — {funding_display} raised"):
                info_col1, info_col2 = st.columns(2)

                with info_col1:
                    st.markdown(f"""
| Field | Value |
|-------|-------|
| **Type** | {row['company_type'] or 'N/A'} |
| **Status** | {row['status'] or 'N/A'} |
| **Founded** | {int(row['founded_year']) if row['founded_year'] else 'N/A'} |
| **HQ** | {row['hq_country'] or 'N/A'} |
| **Employees** | {row['employee_count'] or 'N/A'} |
                    """)

                with info_col2:
                    st.markdown(f"""
| Funding | Value |
|---------|-------|
| **Total Raised** | {funding_display} |
| **Rounds** | {row['funding_rounds']} |
| **Last Funding** | {row['last_funding'] or 'N/A'} |
                    """)
                    if row['website']:
                        st.markdown(f"**Website:** [{row['website']}]({row['website']})")

                # Show funding rounds
                if row['funding_rounds'] > 0:
                    st.markdown("**Funding History:**")
                    rounds_df = run_query("""
                        SELECT round_type, amount_millions, announced_date, lead_investors
                        FROM funding_rounds
                        WHERE company_id = ?
                        ORDER BY announced_date DESC
                    """, (row['id'],))

                    for _, r in rounds_df.iterrows():
                        amount = f"${r['amount_millions']:,.0f}M" if r['amount_millions'] else "Undisclosed"
                        st.markdown(f"- **{r['round_type'] or 'Unknown'}**: {amount} ({r['announced_date'] or 'Date N/A'})")
    else:
        st.info("No companies match the selected filters.")

    # Top funded chart
    st.markdown("---")
    st.subheader("Top 10 Funded Companies")

    top_funded = run_query("""
        SELECT name, total_funding_millions, company_type
        FROM companies
        WHERE total_funding_millions IS NOT NULL AND total_funding_millions > 0
        ORDER BY total_funding_millions DESC
        LIMIT 10
    """)

    if not top_funded.empty:
        fig = px.bar(
            top_funded,
            x='total_funding_millions',
            y='name',
            orientation='h',
            color='company_type',
            labels={'total_funding_millions': 'Total Funding ($ Millions)', 'name': 'Company'},
            title='Top 10 Companies by Total Funding'
        )
        fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)


elif page == "📈 Market Signals":
    st.title("Market Signals & Trends")
    st.markdown("Track funding announcements, partnerships, pain points, and adoption signals.")

    # Check if tables exist
    try:
        funding_count = run_query("SELECT COUNT(*) as count FROM funding_rounds").iloc[0]['count']
        partnership_count = run_query("SELECT COUNT(*) as count FROM partnerships").iloc[0]['count']
        pain_point_count = run_query("SELECT COUNT(*) as count FROM pain_points").iloc[0]['count']
    except:
        st.warning("Market signal tables not found. Run `python scripts/expand_schema.py` to create them.")
        st.stop()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("💰 Funding Rounds", funding_count)
    with col2:
        st.metric("🤝 Partnerships", partnership_count)
    with col3:
        st.metric("⚠️ Pain Points", pain_point_count)
    with col4:
        try:
            adoption_count = run_query("SELECT COUNT(*) as count FROM adoption_signals").iloc[0]['count']
        except:
            adoption_count = 0
        st.metric("📊 Adoption Signals", adoption_count)

    # Tabs for different signal types
    signal_tab1, signal_tab2, signal_tab3 = st.tabs(["💰 Recent Funding", "🤝 Partnerships", "⚠️ Pain Points"])

    with signal_tab1:
        st.subheader("Recent Funding Rounds")

        funding_df = run_query("""
            SELECT
                fr.id,
                c.name as company,
                fr.round_type,
                fr.amount_millions,
                fr.announced_date,
                fr.lead_investors,
                fr.source_url
            FROM funding_rounds fr
            LEFT JOIN companies c ON fr.company_id = c.id
            ORDER BY fr.announced_date DESC, fr.id DESC
            LIMIT 50
        """)

        if not funding_df.empty:
            for _, row in funding_df.iterrows():
                amount = f"${row['amount_millions']:,.0f}M" if row['amount_millions'] else "Undisclosed"
                round_type = row['round_type'] or 'Unknown'

                # Color based on round type
                round_colors = {
                    'seed': '🌱', 'series_a': '🅰️', 'series_b': '🅱️',
                    'series_c': '©️', 'series_d': '🇩', 'series_e': '🇪',
                    'growth': '📈', 'ipo': '🔔', 'acquisition': '🏆'
                }
                emoji = round_colors.get(round_type, '💵')

                st.markdown(f"{emoji} **{row['company'] or 'Unknown Company'}** — **{amount}** ({round_type})")
                st.caption(f"Announced: {row['announced_date'] or 'N/A'} | Lead: {row['lead_investors'] or 'N/A'}")
                if row['source_url']:
                    st.caption(f"[Source]({row['source_url']})")
                st.markdown("---")
        else:
            st.info("No funding rounds recorded yet. Run `python scripts/refresh_data.py --funding` to fetch data.")

        # Funding by round type chart
        funding_by_type = run_query("""
            SELECT round_type, COUNT(*) as count, SUM(amount_millions) as total_millions
            FROM funding_rounds
            WHERE round_type IS NOT NULL
            GROUP BY round_type
            ORDER BY total_millions DESC
        """)

        if not funding_by_type.empty:
            st.subheader("Funding by Round Type")
            fig = px.bar(
                funding_by_type,
                x='round_type',
                y='total_millions',
                color='count',
                labels={'round_type': 'Round Type', 'total_millions': 'Total Amount ($M)', 'count': 'Number of Rounds'},
                title='Total Funding by Round Type'
            )
            st.plotly_chart(fig, use_container_width=True)

    with signal_tab2:
        st.subheader("Strategic Partnerships")

        partnerships_df = run_query("""
            SELECT
                p.id,
                c1.name as company1,
                COALESCE(c2.name, p.company2_name) as company2,
                p.partnership_type,
                p.title,
                p.description,
                p.announcement_date,
                p.source_url
            FROM partnerships p
            LEFT JOIN companies c1 ON p.company1_id = c1.id
            LEFT JOIN companies c2 ON p.company2_id = c2.id
            ORDER BY p.announcement_date DESC, p.id DESC
            LIMIT 30
        """)

        if not partnerships_df.empty:
            for _, row in partnerships_df.iterrows():
                type_emoji = {
                    'integration': '🔗', 'distribution': '📦', 'manufacturing': '🏭',
                    'research': '🔬', 'investment': '💰', 'acquisition': '🏆',
                    'joint_venture': '🤝', 'customer': '👤', 'supplier': '📤'
                }.get(row['partnership_type'], '🤝')

                st.markdown(f"{type_emoji} **{row['company1'] or 'Company'}** ↔ **{row['company2'] or 'Partner'}**")
                if row['title']:
                    st.markdown(f"*{row['title']}*")
                if row['description']:
                    st.caption(row['description'][:200] + ('...' if len(row['description'] or '') > 200 else ''))
                st.caption(f"Type: {row['partnership_type'] or 'N/A'} | Date: {row['announcement_date'] or 'N/A'}")
                if row['source_url']:
                    st.caption(f"[Source]({row['source_url']})")
                st.markdown("---")
        else:
            st.info("No partnerships recorded yet. Run `python scripts/refresh_data.py --partnerships` to fetch data.")

    with signal_tab3:
        st.subheader("Industry Pain Points")

        pain_points_df = run_query("""
            SELECT
                pp.id,
                pp.title,
                pp.category,
                pp.scale,
                pp.severity,
                pp.description,
                pp.potential_solutions,
                pp.frequency_mentioned,
                sec.name as sector,
                src.name as source_name,
                src.url as source_url
            FROM pain_points pp
            LEFT JOIN sectors sec ON pp.sector_id = sec.id
            LEFT JOIN sources src ON pp.source_id = src.id
            ORDER BY pp.severity DESC, pp.frequency_mentioned DESC
            LIMIT 30
        """)

        if not pain_points_df.empty:
            for _, row in pain_points_df.iterrows():
                severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(row['severity'], '⚪')
                category_emoji = {
                    'technical': '⚙️', 'cost': '💰', 'integration': '🔗',
                    'workforce': '👷', 'regulatory': '📜', 'safety': '🛡️',
                    'scalability': '📈', 'reliability': '🔧'
                }.get(row['category'], '❓')

                st.markdown(f"{severity_emoji} {category_emoji} **{row['title']}**")
                st.caption(f"Category: {row['category']} | Severity: {row['severity']} | Scale: {row['scale']} | Sector: {row['sector'] or 'Industry-wide'}")
                if row['description']:
                    st.markdown(row['description'][:300] + ('...' if len(row['description'] or '') > 300 else ''))
                if row['potential_solutions']:
                    st.info(f"**Potential Solutions:** {row['potential_solutions'][:200]}")
                # Show source link
                if row['source_url']:
                    st.markdown(f"📎 **Source:** [{row['source_name'] or 'View Article'}]({row['source_url']})")
                elif row['source_name']:
                    st.caption(f"📎 Source: {row['source_name']}")
                else:
                    st.caption("⚠️ No source link available")
                st.markdown("---")
        else:
            st.info("No pain points recorded yet. Run `python scripts/refresh_data.py --pain-points` to fetch data.")

        # Pain points by category chart
        pain_by_category = run_query("""
            SELECT category, COUNT(*) as count, severity
            FROM pain_points
            WHERE category IS NOT NULL
            GROUP BY category, severity
            ORDER BY count DESC
        """)

        if not pain_by_category.empty:
            st.subheader("Pain Points by Category")
            fig = px.bar(
                pain_by_category,
                x='category',
                y='count',
                color='severity',
                color_discrete_map={'critical': '#dc3545', 'high': '#fd7e14', 'medium': '#ffc107', 'low': '#28a745'},
                labels={'category': 'Category', 'count': 'Count', 'severity': 'Severity'},
                title='Pain Points Distribution'
            )
            st.plotly_chart(fig, use_container_width=True)


elif page == "📤 Import Data":
    st.title("Import Data")
    st.markdown("Import data from meeting transcripts or structured JSON files.")

    # Check for API key
    api_key = get_openrouter_key()
    if not api_key:
        st.warning("**OpenRouter API key required for transcript processing.** Enter your key below or in the AI Query Interface page.")
        api_key_input = st.text_input("OpenRouter API Key", type="password", placeholder="sk-or-v1-...")
        if api_key_input:
            st.session_state.openrouter_key = api_key_input
            st.rerun()

    import_tab1, import_tab2 = st.tabs(["📝 Meeting Transcript", "📁 JSON Import"])

    with import_tab1:
        st.subheader("Extract Data from Meeting Transcript")
        st.markdown("""
        Paste a meeting transcript or notes below. The AI will extract:
        - **Funding announcements** (company, amount, round type)
        - **Partnerships** (companies involved, type, details)
        - **Pain points** (challenges, severity, solutions)
        - **Company information** (new companies mentioned)
        - **Adoption signals** (deployments, pilots, market trends)
        """)

        # Meeting metadata
        col1, col2 = st.columns(2)
        with col1:
            meeting_date = st.date_input("Meeting Date", value=None, help="Date of the meeting")
            meeting_title = st.text_input("Meeting Title/Topic", placeholder="e.g., Q1 Robotics Industry Review")
        with col2:
            meeting_participants = st.text_input("Participants (optional)", placeholder="e.g., John, Sarah, External: Acme Corp")
            meeting_source_url = st.text_input("Source URL (optional)", placeholder="e.g., link to recording or document")

        transcript_text = st.text_area(
            "Paste Meeting Transcript or Notes",
            height=300,
            placeholder="""Paste your meeting transcript here...

Example:
"In today's call, we discussed Figure AI's recent $675M Series B led by Microsoft and OpenAI.
They're valued at $2.6B now. We also talked about the ongoing challenge of safety certification
for humanoid robots - it's a critical pain point that's slowing enterprise adoption.

Sarah mentioned that Amazon is piloting Agility's Digit robots in 3 warehouses,
expanding from their initial 2-warehouse test..."
            """
        )

        if st.button("🔍 Extract Data from Transcript", type="primary", disabled=not api_key):
            if not transcript_text.strip():
                st.error("Please paste a transcript first.")
            else:
                with st.spinner("Analyzing transcript with AI..."):
                    # Build extraction prompt
                    extraction_prompt = f"""Analyze this meeting transcript and extract structured data about the robotics industry.

MEETING TRANSCRIPT:
{transcript_text}

Extract ALL relevant information into these categories. For each item, include specific details mentioned.

Return a JSON object with these arrays (use empty arrays if none found):

{{
  "funding_rounds": [
    {{
      "company_name": "Company that received funding",
      "amount_millions": 123,
      "round_type": "seed|series_a|series_b|series_c|series_d|growth|unknown",
      "announced_date": "YYYY-MM-DD or null",
      "lead_investors": "Investor names",
      "valuation_millions": null,
      "notes": "Additional context from transcript"
    }}
  ],
  "partnerships": [
    {{
      "company1_name": "First company (robotics company)",
      "company2_name": "Partner company",
      "partnership_type": "integration|distribution|manufacturing|research|investment|customer|supplier|other",
      "title": "Brief title",
      "description": "What the partnership involves",
      "notes": "Additional context"
    }}
  ],
  "pain_points": [
    {{
      "title": "Brief title of the challenge",
      "category": "technical|cost|integration|workforce|regulatory|safety|scalability|reliability|other",
      "scale": "startup|smb|mid_market|enterprise|industry_wide",
      "severity": "critical|high|medium|low",
      "description": "Detailed description",
      "potential_solutions": "Any solutions mentioned"
    }}
  ],
  "companies": [
    {{
      "name": "Company name",
      "company_type": "startup|enterprise|public|research",
      "description": "What they do",
      "notes": "Context from meeting"
    }}
  ],
  "adoption_signals": [
    {{
      "title": "Brief description of the signal",
      "signal_type": "deployment|pilot|rfi_rfp|hiring|budget_allocation|expansion|other",
      "company_name": "Company involved",
      "description": "Details",
      "scale_indicator": "e.g., Fortune 500, 10+ locations",
      "sentiment": "positive|neutral|negative"
    }}
  ]
}}

IMPORTANT:
- Only extract information explicitly mentioned in the transcript
- Include dollar amounts in millions (e.g., $675M = 675)
- Use null for unknown values, don't guess
- Include relevant quotes or context in notes fields

Return ONLY valid JSON, no other text."""

                    try:
                        response = requests.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": OPENROUTER_MODEL,
                                "messages": [{"role": "user", "content": extraction_prompt}],
                                "max_tokens": 4000,
                                "temperature": 0.1
                            },
                            timeout=90
                        )
                        response.raise_for_status()
                        ai_response = response.json()['choices'][0]['message']['content']

                        # Parse JSON
                        import re
                        cleaned = ai_response.strip()
                        if '```' in cleaned:
                            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
                            cleaned = re.sub(r'\s*```', '', cleaned)

                        extracted_data = json.loads(cleaned)
                        st.session_state.extracted_data = extracted_data
                        st.session_state.meeting_metadata = {
                            'date': str(meeting_date) if meeting_date else None,
                            'title': meeting_title,
                            'participants': meeting_participants,
                            'source_url': meeting_source_url
                        }
                        st.success("✅ Data extracted successfully! Review below.")

                    except json.JSONDecodeError as e:
                        st.error(f"Failed to parse AI response: {e}")
                        st.text_area("Raw AI Response", ai_response, height=200)
                    except Exception as e:
                        st.error(f"Error: {e}")

        # Display extracted data for review
        if 'extracted_data' in st.session_state and st.session_state.extracted_data:
            st.markdown("---")
            st.subheader("📋 Review Extracted Data")
            st.markdown("Review and edit the extracted data before importing. Uncheck items you don't want to import.")

            extracted = st.session_state.extracted_data
            metadata = st.session_state.get('meeting_metadata', {})

            # Source info
            source_name = f"Meeting: {metadata.get('title', 'Untitled')}" if metadata.get('title') else "Meeting transcript"
            if metadata.get('date'):
                source_name += f" ({metadata.get('date')})"

            st.info(f"**Source:** {source_name}")

            items_to_import = {'funding': [], 'partnerships': [], 'pain_points': [], 'companies': [], 'adoption': []}

            # Funding Rounds
            if extracted.get('funding_rounds'):
                st.markdown("### 💰 Funding Rounds")
                for i, f in enumerate(extracted['funding_rounds']):
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        include = st.checkbox("", value=True, key=f"fund_{i}")
                    with col2:
                        amount = f"${f.get('amount_millions')}M" if f.get('amount_millions') else "Undisclosed"
                        st.markdown(f"**{f.get('company_name', 'Unknown')}** — {amount} ({f.get('round_type', 'unknown')})")
                        if f.get('lead_investors'):
                            st.caption(f"Lead: {f.get('lead_investors')}")
                        if f.get('notes'):
                            st.caption(f"Notes: {f.get('notes')}")
                    if include:
                        items_to_import['funding'].append(f)

            # Partnerships
            if extracted.get('partnerships'):
                st.markdown("### 🤝 Partnerships")
                for i, p in enumerate(extracted['partnerships']):
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        include = st.checkbox("", value=True, key=f"part_{i}")
                    with col2:
                        st.markdown(f"**{p.get('company1_name', '?')}** ↔ **{p.get('company2_name', '?')}** ({p.get('partnership_type', 'other')})")
                        if p.get('description'):
                            st.caption(p.get('description')[:150])
                    if include:
                        items_to_import['partnerships'].append(p)

            # Pain Points
            if extracted.get('pain_points'):
                st.markdown("### ⚠️ Pain Points")
                for i, pp in enumerate(extracted['pain_points']):
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        include = st.checkbox("", value=True, key=f"pain_{i}")
                    with col2:
                        severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(pp.get('severity'), '⚪')
                        st.markdown(f"{severity_emoji} **{pp.get('title', 'Untitled')}** ({pp.get('category', 'other')})")
                        if pp.get('description'):
                            st.caption(pp.get('description')[:150])
                    if include:
                        items_to_import['pain_points'].append(pp)

            # Companies
            if extracted.get('companies'):
                st.markdown("### 🏢 Companies")
                for i, c in enumerate(extracted['companies']):
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        include = st.checkbox("", value=True, key=f"comp_{i}")
                    with col2:
                        st.markdown(f"**{c.get('name', 'Unknown')}** ({c.get('company_type', 'startup')})")
                        if c.get('description'):
                            st.caption(c.get('description')[:100])
                    if include:
                        items_to_import['companies'].append(c)

            # Adoption Signals
            if extracted.get('adoption_signals'):
                st.markdown("### 📊 Adoption Signals")
                for i, a in enumerate(extracted['adoption_signals']):
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        include = st.checkbox("", value=True, key=f"adopt_{i}")
                    with col2:
                        sentiment_emoji = {'positive': '📈', 'neutral': '➡️', 'negative': '📉'}.get(a.get('sentiment'), '➡️')
                        st.markdown(f"{sentiment_emoji} **{a.get('title', 'Untitled')}** ({a.get('signal_type', 'other')})")
                        if a.get('company_name'):
                            st.caption(f"Company: {a.get('company_name')}")
                    if include:
                        items_to_import['adoption'].append(a)

            # Summary and import button
            st.markdown("---")
            total_items = sum(len(v) for v in items_to_import.values())

            if total_items > 0:
                st.markdown(f"**Ready to import {total_items} items:**")
                summary_parts = []
                if items_to_import['funding']:
                    summary_parts.append(f"{len(items_to_import['funding'])} funding rounds")
                if items_to_import['partnerships']:
                    summary_parts.append(f"{len(items_to_import['partnerships'])} partnerships")
                if items_to_import['pain_points']:
                    summary_parts.append(f"{len(items_to_import['pain_points'])} pain points")
                if items_to_import['companies']:
                    summary_parts.append(f"{len(items_to_import['companies'])} companies")
                if items_to_import['adoption']:
                    summary_parts.append(f"{len(items_to_import['adoption'])} adoption signals")
                st.markdown(", ".join(summary_parts))

                if st.button("✅ Import Selected Data", type="primary"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    imported_counts = {'funding': 0, 'partnerships': 0, 'pain_points': 0, 'companies': 0, 'adoption': 0}

                    try:
                        # Create source record for this meeting
                        cursor.execute("""
                            INSERT INTO sources (name, url, source_type, reliability_score)
                            VALUES (?, ?, 'meeting', 0.8)
                        """, (source_name, metadata.get('source_url') or ''))
                        source_id = cursor.lastrowid

                        # Helper to get or create company
                        def get_or_create_company(name, company_type='startup'):
                            cursor.execute("SELECT id FROM companies WHERE name = ?", (name,))
                            result = cursor.fetchone()
                            if result:
                                return result[0]
                            cursor.execute("""
                                INSERT INTO companies (name, company_type, status)
                                VALUES (?, ?, 'active')
                            """, (name, company_type))
                            return cursor.lastrowid

                        # Import companies first
                        for c in items_to_import['companies']:
                            name = c.get('name', '').strip()
                            if name:
                                cursor.execute("SELECT id FROM companies WHERE name = ?", (name,))
                                if not cursor.fetchone():
                                    cursor.execute("""
                                        INSERT INTO companies (name, company_type, description, status)
                                        VALUES (?, ?, ?, 'active')
                                    """, (name, c.get('company_type', 'startup'), c.get('description')))
                                    imported_counts['companies'] += 1

                        # Import funding rounds
                        for f in items_to_import['funding']:
                            company_name = f.get('company_name', '').strip()
                            if company_name and f.get('amount_millions'):
                                company_id = get_or_create_company(company_name)
                                # Check duplicate
                                cursor.execute("""
                                    SELECT id FROM funding_rounds
                                    WHERE company_id = ? AND amount_millions = ?
                                """, (company_id, f.get('amount_millions')))
                                if not cursor.fetchone():
                                    cursor.execute("""
                                        INSERT INTO funding_rounds
                                        (company_id, round_type, amount_millions, announced_date, lead_investors, source_id, notes)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        company_id,
                                        f.get('round_type', 'unknown'),
                                        f.get('amount_millions'),
                                        f.get('announced_date'),
                                        f.get('lead_investors'),
                                        source_id,
                                        f.get('notes')
                                    ))
                                    imported_counts['funding'] += 1

                        # Import partnerships
                        for p in items_to_import['partnerships']:
                            c1_name = p.get('company1_name', '').strip()
                            c2_name = p.get('company2_name', '').strip()
                            if c1_name and c2_name:
                                c1_id = get_or_create_company(c1_name)
                                cursor.execute("""
                                    INSERT INTO partnerships
                                    (company1_id, company2_name, partnership_type, title, description, source_id)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (
                                    c1_id,
                                    c2_name,
                                    p.get('partnership_type', 'other'),
                                    p.get('title'),
                                    p.get('description'),
                                    source_id
                                ))
                                imported_counts['partnerships'] += 1

                        # Import pain points
                        for pp in items_to_import['pain_points']:
                            title = pp.get('title', '').strip()
                            if title:
                                cursor.execute("""
                                    INSERT INTO pain_points
                                    (title, category, scale, severity, description, potential_solutions, source_id, first_identified_date, last_mentioned_date)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'), DATE('now'))
                                """, (
                                    title,
                                    pp.get('category', 'other'),
                                    pp.get('scale', 'industry_wide'),
                                    pp.get('severity', 'medium'),
                                    pp.get('description'),
                                    pp.get('potential_solutions'),
                                    source_id
                                ))
                                imported_counts['pain_points'] += 1

                        # Import adoption signals
                        for a in items_to_import['adoption']:
                            title = a.get('title', '').strip()
                            if title:
                                company_id = None
                                if a.get('company_name'):
                                    company_id = get_or_create_company(a.get('company_name'))
                                cursor.execute("""
                                    INSERT INTO adoption_signals
                                    (title, signal_type, company_id, company_name, description, scale_indicator, sentiment, source_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    title,
                                    a.get('signal_type', 'other'),
                                    company_id,
                                    a.get('company_name'),
                                    a.get('description'),
                                    a.get('scale_indicator'),
                                    a.get('sentiment', 'neutral'),
                                    source_id
                                ))
                                imported_counts['adoption'] += 1

                        # Update company funding totals
                        cursor.execute("""
                            UPDATE companies SET total_funding_millions = (
                                SELECT SUM(amount_millions) FROM funding_rounds WHERE funding_rounds.company_id = companies.id
                            )
                        """)

                        conn.commit()

                        # Show success
                        st.success(f"""✅ **Import Complete!**
- {imported_counts['companies']} companies
- {imported_counts['funding']} funding rounds
- {imported_counts['partnerships']} partnerships
- {imported_counts['pain_points']} pain points
- {imported_counts['adoption']} adoption signals

Source: {source_name}""")

                        # Clear session state
                        del st.session_state.extracted_data
                        if 'meeting_metadata' in st.session_state:
                            del st.session_state.meeting_metadata

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Import failed: {e}")
                    finally:
                        conn.close()
            else:
                st.warning("No items selected for import.")

    with import_tab2:
        st.subheader("Import from JSON File")
        st.markdown("""
        Upload a JSON file with structured data. The file should contain one or more of these arrays:
        - `funding_rounds`
        - `partnerships`
        - `pain_points`
        - `companies`
        - `adoption_signals`
        """)

        st.markdown("**Expected JSON format:**")
        with st.expander("View JSON Schema"):
            st.code('''{
  "source": {
    "name": "Source name (required)",
    "url": "https://source-url.com",
    "type": "report|news|meeting|company"
  },
  "funding_rounds": [
    {
      "company_name": "Company Name",
      "amount_millions": 100,
      "round_type": "series_a",
      "announced_date": "2025-01-15",
      "lead_investors": "Investor A, Investor B"
    }
  ],
  "partnerships": [
    {
      "company1_name": "Robotics Co",
      "company2_name": "Partner Co",
      "partnership_type": "integration",
      "title": "Partnership title",
      "description": "Details..."
    }
  ],
  "pain_points": [
    {
      "title": "Pain point title",
      "category": "technical",
      "severity": "high",
      "scale": "enterprise",
      "description": "Details...",
      "potential_solutions": "Solutions..."
    }
  ]
}''', language='json')

        uploaded_file = st.file_uploader("Upload JSON file", type=['json'])

        if uploaded_file:
            try:
                json_data = json.load(uploaded_file)
                st.success(f"✅ Loaded JSON file: {uploaded_file.name}")

                # Show preview
                st.markdown("**Preview:**")
                for key in ['funding_rounds', 'partnerships', 'pain_points', 'companies', 'adoption_signals']:
                    if key in json_data and json_data[key]:
                        st.markdown(f"- **{key}**: {len(json_data[key])} items")

                source_info = json_data.get('source', {})
                source_name = source_info.get('name', uploaded_file.name)
                source_url = source_info.get('url', '')

                st.info(f"**Source:** {source_name}")

                if st.button("✅ Import JSON Data", type="primary"):
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    try:
                        # Create source
                        cursor.execute("""
                            INSERT INTO sources (name, url, source_type, reliability_score)
                            VALUES (?, ?, ?, 0.7)
                        """, (source_name, source_url, source_info.get('type', 'report')))
                        source_id = cursor.lastrowid

                        def get_or_create_company(name, company_type='startup'):
                            cursor.execute("SELECT id FROM companies WHERE name = ?", (name,))
                            result = cursor.fetchone()
                            if result:
                                return result[0]
                            cursor.execute("INSERT INTO companies (name, company_type, status) VALUES (?, ?, 'active')", (name, company_type))
                            return cursor.lastrowid

                        counts = {'funding': 0, 'partnerships': 0, 'pain_points': 0, 'companies': 0, 'adoption': 0}

                        # Import each type
                        for f in json_data.get('funding_rounds', []):
                            if f.get('company_name') and f.get('amount_millions'):
                                company_id = get_or_create_company(f['company_name'])
                                cursor.execute("""
                                    INSERT INTO funding_rounds (company_id, round_type, amount_millions, announced_date, lead_investors, source_id)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (company_id, f.get('round_type', 'unknown'), f['amount_millions'], f.get('announced_date'), f.get('lead_investors'), source_id))
                                counts['funding'] += 1

                        for p in json_data.get('partnerships', []):
                            if p.get('company1_name') and p.get('company2_name'):
                                c1_id = get_or_create_company(p['company1_name'])
                                cursor.execute("""
                                    INSERT INTO partnerships (company1_id, company2_name, partnership_type, title, description, source_id)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (c1_id, p['company2_name'], p.get('partnership_type', 'other'), p.get('title'), p.get('description'), source_id))
                                counts['partnerships'] += 1

                        for pp in json_data.get('pain_points', []):
                            if pp.get('title'):
                                cursor.execute("""
                                    INSERT INTO pain_points (title, category, scale, severity, description, potential_solutions, source_id, first_identified_date, last_mentioned_date)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'), DATE('now'))
                                """, (pp['title'], pp.get('category', 'other'), pp.get('scale', 'industry_wide'), pp.get('severity', 'medium'), pp.get('description'), pp.get('potential_solutions'), source_id))
                                counts['pain_points'] += 1

                        for c in json_data.get('companies', []):
                            if c.get('name'):
                                cursor.execute("SELECT id FROM companies WHERE name = ?", (c['name'],))
                                if not cursor.fetchone():
                                    cursor.execute("INSERT INTO companies (name, company_type, description, status) VALUES (?, ?, ?, 'active')",
                                                 (c['name'], c.get('company_type', 'startup'), c.get('description')))
                                    counts['companies'] += 1

                        for a in json_data.get('adoption_signals', []):
                            if a.get('title'):
                                company_id = get_or_create_company(a['company_name']) if a.get('company_name') else None
                                cursor.execute("""
                                    INSERT INTO adoption_signals (title, signal_type, company_id, company_name, description, scale_indicator, sentiment, source_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (a['title'], a.get('signal_type', 'other'), company_id, a.get('company_name'), a.get('description'), a.get('scale_indicator'), a.get('sentiment', 'neutral'), source_id))
                                counts['adoption'] += 1

                        cursor.execute("""
                            UPDATE companies SET total_funding_millions = (
                                SELECT SUM(amount_millions) FROM funding_rounds WHERE funding_rounds.company_id = companies.id
                            )
                        """)

                        conn.commit()
                        st.success(f"""✅ **Import Complete!**
- {counts['companies']} companies
- {counts['funding']} funding rounds
- {counts['partnerships']} partnerships
- {counts['pain_points']} pain points
- {counts['adoption']} adoption signals""")

                    except Exception as e:
                        conn.rollback()
                        st.error(f"Import failed: {e}")
                    finally:
                        conn.close()

            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON file: {e}")


elif page == "🔍 Data Explorer":
    st.title("Data Explorer")

    # Filters
    st.subheader("Filters")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sectors = run_query("SELECT name FROM sectors ORDER BY name")
        sector_filter = st.selectbox(
            "Sector",
            ["All"] + sectors['name'].tolist()
        )

    with col2:
        dimensions = run_query("SELECT name FROM dimensions ORDER BY name")
        dimension_filter = st.selectbox(
            "Dimension",
            ["All"] + dimensions['name'].tolist()
        )

    with col3:
        confidence_filter = st.selectbox(
            "Confidence",
            ["All", "high", "medium", "low", "unverified"]
        )

    with col4:
        validation_filter = st.selectbox(
            "Validation Status",
            ["All", "validated", "pending", "in_review", "rejected", "outdated"]
        )

    # Build query with filters
    query = """
        SELECT
            dp.id,
            s.name as sector,
            sc.name as subcategory,
            d.name as dimension,
            d.unit,
            dp.value,
            dp.value_text,
            dp.year,
            dp.quarter,
            dp.confidence,
            dp.validation_status,
            src.name as source,
            dp.notes,
            dp.created_at
        FROM data_points dp
        LEFT JOIN sectors s ON dp.sector_id = s.id
        LEFT JOIN subcategories sc ON dp.subcategory_id = sc.id
        LEFT JOIN dimensions d ON dp.dimension_id = d.id
        LEFT JOIN sources src ON dp.source_id = src.id
        WHERE 1=1
    """
    params = []

    if sector_filter != "All":
        query += " AND s.name = ?"
        params.append(sector_filter)

    if dimension_filter != "All":
        query += " AND d.name = ?"
        params.append(dimension_filter)

    if confidence_filter != "All":
        query += " AND dp.confidence = ?"
        params.append(confidence_filter)

    if validation_filter != "All":
        query += " AND dp.validation_status = ?"
        params.append(validation_filter)

    query += " ORDER BY dp.created_at DESC LIMIT 500"

    # Execute query
    df = run_query(query, tuple(params))

    # Display results
    st.markdown("---")
    st.subheader(f"Data Points ({len(df)} records)")

    if not df.empty:
        # Format the dataframe for display
        display_df = df.copy()

        # Combine value columns
        display_df['value_display'] = display_df.apply(
            lambda row: f"{row['value']:.2f} {row['unit']}" if pd.notna(row['value'])
            else (row['value_text'] if pd.notna(row['value_text']) else 'N/A'),
            axis=1
        )

        # Select columns to display
        display_cols = ['sector', 'subcategory', 'dimension', 'value_display',
                       'year', 'confidence', 'validation_status', 'source', 'notes']

        st.dataframe(
            display_df[display_cols],
            width='stretch',
            height=500,
            column_config={
                'sector': st.column_config.TextColumn('Sector', width='medium'),
                'subcategory': st.column_config.TextColumn('Subcategory', width='medium'),
                'dimension': st.column_config.TextColumn('Dimension', width='medium'),
                'value_display': st.column_config.TextColumn('Value', width='medium'),
                'year': st.column_config.NumberColumn('Year', format='%d'),
                'confidence': st.column_config.TextColumn('Confidence', width='small'),
                'validation_status': st.column_config.TextColumn('Status', width='small'),
                'source': st.column_config.TextColumn('Source', width='medium'),
                'notes': st.column_config.TextColumn('Notes', width='large'),
            }
        )

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="robotics_data_export.csv",
            mime="text/csv"
        )
    else:
        st.info("No data points match the selected filters.")

    # Technology data section
    st.markdown("---")
    st.subheader("Technology Data")

    tech_query = """
        SELECT
            t.name as technology,
            t.category,
            t.maturity_level,
            d.name as dimension,
            d.unit,
            tdp.value,
            tdp.year,
            tdp.confidence
        FROM technology_data_points tdp
        JOIN technologies t ON tdp.technology_id = t.id
        JOIN dimensions d ON tdp.dimension_id = d.id
        ORDER BY t.category, t.name
    """
    tech_df = run_query(tech_query)

    if not tech_df.empty:
        st.dataframe(tech_df, width='stretch', height=300)
    else:
        st.info("No technology data points available yet.")


elif page == "📑 Technical Intelligence":
    st.title("Technical Intelligence Reports")
    st.markdown("Deep-dive analysis of breakthroughs, R&D activity, patents, and technical hurdles by sector.")

    # Get list of reports
    reports_dir = project_root / "data" / "reports"

    if reports_dir.exists():
        report_files = list(reports_dir.glob("*_technical_intelligence.md"))

        if report_files:
            # Create sector selector
            sector_names = {
                "agricultural_robotics": "Agricultural Robotics",
                "construction_robotics": "Construction Robotics",
                "industrial_robotics": "Industrial Robotics",
                "logistics_robotics": "Logistics Robotics",
                "mobile_robotics": "Mobile Robotics",
                "service_robotics": "Service Robotics"
            }

            # Build options from available files
            available_sectors = []
            for f in sorted(report_files):
                key = f.stem.replace("_technical_intelligence", "")
                if key in sector_names:
                    available_sectors.append((sector_names[key], f))

            if available_sectors:
                selected_sector = st.selectbox(
                    "Select Sector",
                    options=[name for name, _ in available_sectors],
                    index=0
                )

                # Find the matching file
                selected_file = None
                for name, f in available_sectors:
                    if name == selected_sector:
                        selected_file = f
                        break

                if selected_file and selected_file.exists():
                    st.markdown("---")

                    # Read and display the report
                    content = selected_file.read_text(encoding='utf-8')

                    # Display report sections
                    st.markdown(content)

                    # Download button
                    st.markdown("---")
                    st.download_button(
                        label=f"📥 Download {selected_sector} Report",
                        data=content,
                        file_name=selected_file.name,
                        mime="text/markdown"
                    )
            else:
                st.warning("No reports found in the expected format.")
        else:
            st.info("No technical intelligence reports available yet.")
            st.markdown("""
            Run the expansion script to generate reports:
            ```bash
            python expand_robotics_db.py
            # Select option 4: Research technical innovations & R&D
            ```
            """)
    else:
        st.info("Reports directory not found. Creating...")
        reports_dir.mkdir(parents=True, exist_ok=True)
        st.markdown("Please add technical intelligence reports to `data/reports/`")


elif page == "✅ Validation":
    st.title("Data Validation Workflow")
    st.markdown("Review and validate AI-generated data points and sources.")

    # Tabs for different validation tasks
    val_tab1, val_tab2, val_tab3 = st.tabs(["📊 Data Points", "🔗 Sources", "📈 Statistics"])

    with val_tab1:
        st.subheader("Validate Data Points")

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            val_status_filter = st.selectbox(
                "Validation Status",
                ["pending", "All", "in_review", "validated", "rejected", "outdated"],
                key="dp_val_status"
            )

        with col2:
            conf_filter = st.selectbox(
                "Confidence Level",
                ["All", "high", "medium", "low", "unverified"],
                key="dp_conf"
            )

        with col3:
            sector_list = run_query("SELECT name FROM sectors ORDER BY name")
            sector_filter_val = st.selectbox(
                "Sector",
                ["All"] + sector_list['name'].tolist(),
                key="dp_sector"
            )

        # Build query with more details
        dp_query = """
            SELECT
                dp.id,
                dp.sector_id,
                s.name as sector,
                dp.subcategory_id,
                sub.name as subcategory,
                dp.dimension_id,
                d.name as dimension,
                d.unit as dimension_unit,
                dp.value,
                dp.value_text,
                dp.year,
                dp.confidence,
                dp.validation_status,
                dp.source_id,
                src.name as source_name,
                src.url as source_url,
                src.source_type,
                dp.notes
            FROM data_points dp
            LEFT JOIN sectors s ON dp.sector_id = s.id
            LEFT JOIN subcategories sub ON dp.subcategory_id = sub.id
            LEFT JOIN dimensions d ON dp.dimension_id = d.id
            LEFT JOIN sources src ON dp.source_id = src.id
            WHERE 1=1
        """
        params = []

        if val_status_filter != "All":
            dp_query += " AND dp.validation_status = ?"
            params.append(val_status_filter)

        if conf_filter != "All":
            dp_query += " AND dp.confidence = ?"
            params.append(conf_filter)

        if sector_filter_val != "All":
            dp_query += " AND s.name = ?"
            params.append(sector_filter_val)

        dp_query += " ORDER BY dp.id DESC LIMIT 100"

        dp_df = run_query(dp_query, tuple(params))

        # Get lookup data for dropdowns
        all_sectors = run_query("SELECT id, name FROM sectors ORDER BY name")
        all_dimensions = run_query("SELECT id, name, unit FROM dimensions ORDER BY name")
        all_subcategories = run_query("SELECT id, sector_id, name FROM subcategories ORDER BY name")

        st.markdown(f"**{len(dp_df)} data points** matching filters")

        if not dp_df.empty:
            for idx, row in dp_df.iterrows():
                with st.expander(f"ID {row['id']}: {row['sector']} → {row['subcategory'] or 'General'} | {row['dimension']}"):

                    # Current Data Display (Clear formatting)
                    st.markdown("### 📊 Current Data")

                    info_col1, info_col2 = st.columns(2)

                    with info_col1:
                        st.markdown(f"""
| Field | Value |
|-------|-------|
| **ID** | {row['id']} |
| **Sector** | {row['sector']} |
| **Subcategory** | {row['subcategory'] or '(none)'} |
| **Metric Type** | {row['dimension']} |
| **Unit** | {row['dimension_unit'] or 'see value_text'} |
                        """)

                    with info_col2:
                        # Format value with unit interpretation
                        unit = row['dimension_unit'] or ''
                        val = row['value']
                        val_text = row['value_text'] or ''

                        if row['dimension'] == 'market_size':
                            interpreted = f"${val} billion USD" if val else val_text
                        elif row['dimension'] == 'market_growth_rate':
                            interpreted = f"{val}% CAGR" if val else val_text
                        elif row['dimension'] == 'average_price':
                            interpreted = f"${val:,.0f} USD per unit" if val else val_text
                        elif row['dimension'] == 'r&d_investment':
                            interpreted = f"${val} million USD" if val else val_text
                        elif row['dimension'] == 'unit_shipments':
                            interpreted = f"{val:,.0f} units" if val else val_text
                        elif row['dimension'] == 'adoption_rate':
                            interpreted = f"{val}%" if val else val_text
                        elif row['dimension'] == 'roi_timeline':
                            interpreted = f"{val} months" if val else val_text
                        elif row['dimension'] == 'patents_filed':
                            interpreted = f"{val:,.0f} patents" if val else val_text
                        else:
                            interpreted = val_text if val_text else str(val)

                        # Safely convert year (might be float, NaN, or None)
                        try:
                            year_display = int(row['year']) if row['year'] and not pd.isna(row['year']) else 'N/A'
                        except (ValueError, TypeError):
                            year_display = 'N/A'

                        st.markdown(f"""
| Field | Value |
|-------|-------|
| **Numeric Value** | {val} |
| **Original Text** | {val_text or '(none)'} |
| **Interpreted As** | **{interpreted}** |
| **Year** | {year_display} |
                        """)

                    # Source Information with enrichment badges
                    st.markdown("### 🔗 Source Information")

                    source_name = row['source_name'] or 'Unknown'

                    # Detect company type from source name
                    if source_name.startswith('[STARTUP]'):
                        company_badge = "🚀 **STARTUP**"
                        company_type = "startup"
                    elif source_name.startswith('[') and ']' in source_name:
                        company_name = source_name[1:source_name.index(']')]
                        company_badge = f"🏢 **{company_name}**"
                        company_type = "established"
                    else:
                        company_badge = "📊 Research/Report"
                        company_type = "research"

                    # Detect verification status from notes
                    notes = row['notes'] or ''
                    if 'REQUIRES HUMAN VERIFICATION' in notes:
                        verification_badge = "⚠️ Needs Human Review"
                        verification_color = "warning"
                    elif 'VERIFIED' in notes or row['confidence'] == 'high':
                        verification_badge = "✅ Verified Source"
                        verification_color = "success"
                    elif 'PARTIAL' in notes or row['confidence'] == 'medium':
                        verification_badge = "🔍 Partially Verified"
                        verification_color = "info"
                    else:
                        verification_badge = "❓ Unverified"
                        verification_color = "error"

                    src_col1, src_col2 = st.columns(2)

                    with src_col1:
                        st.markdown(f"**Company Type:** {company_badge}")
                        st.markdown(f"**Source:** {source_name[:60]}{'...' if len(source_name) > 60 else ''}")
                        st.markdown(f"**Data Type:** `{row['source_type'] or 'unknown'}`")

                    with src_col2:
                        # Show verification status with appropriate styling
                        if verification_color == "success":
                            st.success(verification_badge)
                        elif verification_color == "info":
                            st.info(verification_badge)
                        elif verification_color == "warning":
                            st.warning(verification_badge)
                        else:
                            st.error(verification_badge)

                        st.markdown(f"**Confidence:** `{row['confidence'] or 'unverified'}`")

                    # URL section with smart detection
                    if row['source_url']:
                        url = row['source_url']
                        # Check if it's a specific document vs generic homepage
                        is_document = any(x in url.lower() for x in ['.pdf', '/report', '/filing', '/annual', 'sec.gov', 'q4cdn', 'press', 'news'])

                        if is_document:
                            st.success(f"📄 **Specific Document:** [{url[:70]}...]({url})")
                        else:
                            st.warning(f"🏠 **Website (may need to search for data):** [{url[:50]}...]({url})")
                    else:
                        st.error("❌ No URL available - requires manual research")

                    # Notes with parsed verification details
                    if notes:
                        # Extract verification notes if present
                        if '[Verification:' in notes:
                            st.markdown("**Verification Notes:**")
                            st.caption(notes[:500] + ('...' if len(notes) > 500 else ''))
                        else:
                            st.markdown(f"**Notes:** {notes[:300]}{'...' if len(notes) > 300 else ''}")

                    st.markdown("---")

                    # Edit Section
                    st.markdown("### ✏️ Edit Data Point")

                    edit_col1, edit_col2 = st.columns(2)

                    with edit_col1:
                        # Editable fields
                        new_value = st.number_input(
                            "Numeric Value",
                            value=float(row['value']) if row['value'] else 0.0,
                            key=f"val_{row['id']}"
                        )

                        new_value_text = st.text_input(
                            "Value Text (with units)",
                            value=row['value_text'] or "",
                            key=f"valtxt_{row['id']}",
                            help="E.g., '120,000 units shipped globally' or '$4.2B market size'"
                        )

                        # Safely get year value
                        try:
                            year_val = int(row['year']) if row['year'] and not pd.isna(row['year']) else 2024
                        except (ValueError, TypeError):
                            year_val = 2024

                        new_year = st.number_input(
                            "Year",
                            value=year_val,
                            min_value=2000,
                            max_value=2035,
                            key=f"year_{row['id']}"
                        )

                        new_notes = st.text_area(
                            "Notes",
                            value=row['notes'] or "",
                            key=f"notes_{row['id']}",
                            help="Add context, caveats, or validation notes"
                        )

                    with edit_col2:
                        new_status = st.selectbox(
                            "Validation Status",
                            ["pending", "in_review", "validated", "rejected", "outdated"],
                            index=["pending", "in_review", "validated", "rejected", "outdated"].index(row['validation_status']) if row['validation_status'] in ["pending", "in_review", "validated", "rejected", "outdated"] else 0,
                            key=f"status_{row['id']}"
                        )

                        new_conf = st.selectbox(
                            "Confidence Level",
                            ["high", "medium", "low", "unverified"],
                            index=["high", "medium", "low", "unverified"].index(row['confidence']) if row['confidence'] in ["high", "medium", "low", "unverified"] else 1,
                            key=f"conf_{row['id']}",
                            help="high=verified source, medium=credible estimate, low=uncertain, unverified=needs review"
                        )

                        # Sector dropdown
                        sector_options = all_sectors['name'].tolist()
                        current_sector_idx = sector_options.index(row['sector']) if row['sector'] in sector_options else 0
                        new_sector = st.selectbox(
                            "Sector",
                            sector_options,
                            index=current_sector_idx,
                            key=f"sector_{row['id']}"
                        )

                        # Get subcategories for selected sector
                        new_sector_id = all_sectors[all_sectors['name'] == new_sector]['id'].iloc[0]
                        sector_subcats = all_subcategories[all_subcategories['sector_id'] == new_sector_id]['name'].tolist()
                        sector_subcats = ['(none)'] + sector_subcats

                        current_subcat = row['subcategory'] if row['subcategory'] else '(none)'
                        current_subcat_idx = sector_subcats.index(current_subcat) if current_subcat in sector_subcats else 0

                        new_subcategory = st.selectbox(
                            "Subcategory",
                            sector_subcats,
                            index=current_subcat_idx,
                            key=f"subcat_{row['id']}"
                        )

                    # Save button
                    if st.button("💾 Save All Changes", key=f"save_{row['id']}", type="primary"):
                        conn = get_db_connection()
                        cursor = conn.cursor()

                        # Get new IDs
                        new_sector_id = all_sectors[all_sectors['name'] == new_sector]['id'].iloc[0]

                        new_subcat_id = None
                        if new_subcategory != '(none)':
                            subcat_match = all_subcategories[(all_subcategories['name'] == new_subcategory) & (all_subcategories['sector_id'] == new_sector_id)]
                            if not subcat_match.empty:
                                new_subcat_id = subcat_match['id'].iloc[0]

                        cursor.execute("""
                            UPDATE data_points
                            SET value = ?, value_text = ?, year = ?, notes = ?,
                                validation_status = ?, confidence = ?,
                                sector_id = ?, subcategory_id = ?,
                                validated_at = CURRENT_TIMESTAMP,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_value, new_value_text, new_year, new_notes,
                              new_status, new_conf, new_sector_id, new_subcat_id, row['id']))
                        conn.commit()
                        st.success(f"✅ Updated data point ID {row['id']}")
                        st.rerun()

    with val_tab2:
        st.subheader("Validate Sources")

        st.info("""
        **Source Validation Guide:**
        - **ai_generated** sources need URLs and verification
        - Distinguish between **Company Homepage** (e.g., irobot.com) and **Specific Report** (e.g., irobot.com/investor-relations/annual-report-2024.pdf)
        - Reliability: 0.0 = Unreliable, 0.5 = Needs verification, 0.8+ = Verified/trusted
        """)

        # Source type filter
        source_type_filter = st.selectbox(
            "Filter by Source Type",
            ["ai_generated", "All", "research_report", "news", "company", "government", "academic"],
            key="src_type"
        )

        # Build source query with more details
        src_query = """
            SELECT
                s.id,
                s.name,
                s.url,
                s.source_type,
                s.reliability_score,
                (SELECT COUNT(*) FROM data_points WHERE source_id = s.id) as data_point_count
            FROM sources s
            WHERE 1=1
        """
        src_params = []

        if source_type_filter != "All":
            src_query += " AND s.source_type = ?"
            src_params.append(source_type_filter)

        src_query += " ORDER BY data_point_count DESC, s.id DESC LIMIT 50"

        src_df = run_query(src_query, tuple(src_params))

        st.markdown(f"**{len(src_df)} sources** matching filters (sorted by usage)")

        if not src_df.empty:
            for idx, row in src_df.iterrows():
                # Determine status icon
                status_icon = "⚠️" if row['source_type'] == 'ai_generated' else ("✅" if row['reliability_score'] and row['reliability_score'] >= 0.7 else "🔍")

                with st.expander(f"{status_icon} Source #{row['id']}: {row['name'][:50]}{'...' if len(row['name']) > 50 else ''} — {row['data_point_count']} data points"):

                    # ===== CURRENT SOURCE INFO =====
                    st.markdown("### 📋 Current Source Information")

                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.markdown(f"**Source Name:** {row['name']}")
                        st.markdown(f"**Type:** `{row['source_type']}`")
                    with info_col2:
                        reliability = row['reliability_score'] if row['reliability_score'] else 0.5
                        reliability_label = "Unreliable" if reliability < 0.4 else ("Needs Review" if reliability < 0.7 else "Trusted")
                        st.markdown(f"**Reliability:** {reliability:.1f} ({reliability_label})")
                        st.markdown(f"**Data Points Using This:** {row['data_point_count']}")

                    # URL status
                    current_url = row['url'] or ""
                    # Check if it's a generic homepage vs specific report
                    is_generic = True  # Default to generic if no URL
                    if current_url:
                        is_generic = not any(x in current_url.lower() for x in ['report', 'pdf', 'research', 'press', 'news', 'article', 'publication', 'investor', 'annual'])
                        if is_generic:
                            st.warning(f"⚠️ **Generic URL detected:** [{current_url}]({current_url}) - This appears to be a company homepage, not a specific report")
                        else:
                            st.success(f"✅ **Report URL:** [{current_url}]({current_url})")
                    else:
                        st.error("❌ **No URL set** - This source needs a URL")

                    # ===== DATA POINTS USING THIS SOURCE =====
                    st.markdown("### 📊 Data Points Using This Source")
                    related_dp = run_query("""
                        SELECT
                            dp.id,
                            sec.name as sector,
                            dim.name as dimension,
                            dp.value,
                            dp.value_text,
                            dp.year
                        FROM data_points dp
                        JOIN sectors sec ON dp.sector_id = sec.id
                        JOIN dimensions dim ON dp.dimension_id = dim.id
                        WHERE dp.source_id = ?
                        LIMIT 5
                    """, (row['id'],))

                    if not related_dp.empty:
                        # Show a summary of what data uses this source
                        for _, dp in related_dp.iterrows():
                            value_display = dp['value_text'] if dp['value_text'] else str(dp['value'])
                            st.markdown(f"- **{dp['sector']}** → {dp['dimension']}: {value_display} ({dp['year']})")

                        if row['data_point_count'] > 5:
                            st.caption(f"...and {row['data_point_count'] - 5} more data points")
                    else:
                        st.caption("No data points currently using this source")

                    # ===== EDIT SECTION =====
                    st.markdown("### ✏️ Edit Source")

                    edit_col1, edit_col2 = st.columns(2)

                    with edit_col1:
                        new_name = st.text_input(
                            "Source Name",
                            value=row['name'],
                            key=f"name_{row['id']}",
                            help="e.g., 'IFR World Robotics 2024' or 'McKinsey Global Institute'"
                        )

                        new_type = st.selectbox(
                            "Source Type",
                            ["ai_generated", "research_report", "news", "company", "government", "academic"],
                            index=["ai_generated", "research_report", "news", "company", "government", "academic"].index(row['source_type']) if row['source_type'] in ["ai_generated", "research_report", "news", "company", "government", "academic"] else 0,
                            key=f"type_{row['id']}",
                            help="ai_generated = Not verified | research_report = Industry report | company = Company disclosure"
                        )

                    with edit_col2:
                        new_reliability = st.slider(
                            "Reliability Score",
                            0.0, 1.0,
                            value=float(row['reliability_score']) if row['reliability_score'] else 0.5,
                            step=0.1,
                            key=f"rel_{row['id']}",
                            help="0.0 = Unreliable | 0.5 = Unverified | 0.8+ = Verified/trusted source"
                        )

                    st.markdown("**URLs:**")
                    url_col1, url_col2 = st.columns(2)

                    with url_col1:
                        # If URL looks like a specific report, pre-fill it here
                        report_url_value = current_url if (current_url and not is_generic) else ""
                        new_url = st.text_input(
                            "Specific Report/Article URL",
                            value=report_url_value,
                            key=f"url_{row['id']}",
                            help="Direct link to the specific report, PDF, or article containing the data"
                        )

                    with url_col2:
                        # If URL looks generic (homepage), pre-fill it here
                        homepage_url_value = current_url if (current_url and is_generic) else ""
                        company_url = st.text_input(
                            "Company/Publisher Homepage (optional)",
                            value=homepage_url_value,
                            key=f"compurl_{row['id']}",
                            help="e.g., irobot.com or mckinsey.com - used if no specific report URL is available"
                        )

                    # Use specific URL if provided, otherwise fall back to company URL
                    final_url = new_url.strip() if new_url.strip() else company_url.strip()

                    if st.button("💾 Save Changes", key=f"save_src_{row['id']}"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE sources
                            SET name = ?, url = ?, source_type = ?, reliability_score = ?
                            WHERE id = ?
                        """, (new_name, final_url, new_type, new_reliability, row['id']))
                        conn.commit()
                        st.success(f"✅ Updated source #{row['id']}")
                        st.rerun()

    with val_tab3:
        st.subheader("Validation Statistics")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Data Point Validation Status**")
            val_stats = run_query("""
                SELECT validation_status, COUNT(*) as count,
                       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM data_points), 1) as percent
                FROM data_points
                GROUP BY validation_status
                ORDER BY count DESC
            """)
            st.dataframe(val_stats, hide_index=True, use_container_width=True)

            # Progress bar
            validated_count = val_stats[val_stats['validation_status'] == 'validated']['count'].sum() if 'validated' in val_stats['validation_status'].values else 0
            total_count = val_stats['count'].sum()
            progress = validated_count / total_count if total_count > 0 else 0
            st.progress(progress, text=f"{validated_count}/{total_count} validated ({progress*100:.1f}%)")

        with col2:
            st.markdown("**Source Types**")
            src_stats = run_query("""
                SELECT source_type, COUNT(*) as count,
                       ROUND(AVG(reliability_score), 2) as avg_reliability
                FROM sources
                GROUP BY source_type
                ORDER BY count DESC
            """)
            st.dataframe(src_stats, hide_index=True, use_container_width=True)

        st.markdown("---")

        st.markdown("**Confidence Level Distribution**")
        conf_stats = run_query("""
            SELECT confidence, COUNT(*) as count
            FROM data_points
            GROUP BY confidence
            ORDER BY count DESC
        """)

        import plotly.express as px
        fig = px.pie(conf_stats, values='count', names='confidence', title='Data Points by Confidence')
        st.plotly_chart(fig, use_container_width=True)

        # Quick actions
        st.markdown("---")
        st.subheader("Bulk Actions")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Mark all 'high' confidence as 'validated'"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE data_points
                    SET validation_status = 'validated', validated_at = CURRENT_TIMESTAMP
                    WHERE confidence = 'high' AND validation_status = 'pending'
                """)
                affected = cursor.rowcount
                conn.commit()
                st.success(f"Updated {affected} data points")

        with col2:
            if st.button("🔄 Upgrade 'ai_generated' sources with URLs to 'research_report'"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sources
                    SET source_type = 'research_report', reliability_score = 0.7
                    WHERE source_type = 'ai_generated' AND url IS NOT NULL AND url != ''
                """)
                affected = cursor.rowcount
                conn.commit()
                st.success(f"Updated {affected} sources")


elif page == "📋 Methodology":
    st.title("Data Methodology")
    st.markdown("How data is collected, categorized, and interpreted in this database.")

    st.markdown("---")

    # Data Collection
    st.header("1. Data Collection Process")
    st.markdown("""
    Data points are collected using **Kimi K2.5** AI via the OpenRouter API. The AI:
    1. Searches for quantitative robotics industry data
    2. Extracts specific metrics with sources
    3. Returns structured data in a consistent format

    Each data point includes:
    - **Sector** and **Subcategory** classification
    - **Dimension** (metric type)
    - **Value** (numeric) and **Value Text** (original with units)
    - **Year**, **Source**, and **Confidence Level**
    """)

    st.markdown("---")

    # Dimension Reference
    st.header("2. Dimension Reference (How to Interpret Values)")

    dimension_query = """
        SELECT name, unit, description,
               (SELECT COUNT(*) FROM data_points WHERE dimension_id = dimensions.id) as count
        FROM dimensions
        WHERE name NOT IN ('[correct enum]')
        ORDER BY count DESC
    """
    dim_df = run_query(dimension_query)

    st.markdown("Each dimension has a specific unit of measurement:")

    st.dataframe(
        dim_df,
        column_config={
            'name': st.column_config.TextColumn('Dimension', width='medium'),
            'unit': st.column_config.TextColumn('Unit', width='small'),
            'description': st.column_config.TextColumn('Description', width='large'),
            'count': st.column_config.NumberColumn('Data Points', format='%d')
        },
        hide_index=True,
        use_container_width=True
    )

    st.markdown("""
    **Interpreting Values:**

    | Dimension | Value Example | Interpretation |
    |-----------|---------------|----------------|
    | `market_size` | 4.2 | **$4.2 billion** USD |
    | `market_growth_rate` | 23.5 | **23.5% CAGR** (compound annual growth rate) |
    | `unit_shipments` | 125000 | **125,000 units** shipped |
    | `average_price` | 15000 | **$15,000 USD** per unit |
    | `r&d_investment` | 35 | **$35 million** USD investment |
    | `adoption_rate` | 34 | **34%** market penetration |
    | `roi_timeline` | 18 | **18 months** payback period |
    | `patents_filed` | 1247 | **1,247 patents** filed |
    | `performance_metric` | varies | See `value_text` for specific metric and units |
    | `technical_capability` | varies | See `value_text` for specific capability |

    **Note:** For dimensions marked "varies", always check the `value_text` column for the original
    text with units (e.g., "99.2% accuracy" or "50kg payload capacity").
    """)

    st.markdown("---")

    # Confidence Levels
    st.header("3. Confidence Levels")

    st.markdown("""
    | Level | Meaning | Source Quality |
    |-------|---------|----------------|
    | **high** | Verified from authoritative source | Company reports, peer-reviewed research, government data |
    | **medium** | Reasonable estimate from credible source | Industry reports, news articles, analyst estimates |
    | **low** | Uncertain or speculative | Blog posts, unverified claims, rough estimates |
    | **unverified** | Not yet validated | AI-generated, needs review |
    """)

    conf_query = """
        SELECT confidence, COUNT(*) as count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM data_points), 1) as percent
        FROM data_points
        GROUP BY confidence
        ORDER BY count DESC
    """
    conf_df = run_query(conf_query)
    st.dataframe(conf_df, hide_index=True)

    st.markdown("---")

    # Validation Status
    st.header("4. Validation Status")

    st.markdown("""
    | Status | Meaning |
    |--------|---------|
    | **pending** | Awaiting review |
    | **in_review** | Currently being validated |
    | **validated** | Confirmed accurate |
    | **rejected** | Found to be inaccurate |
    | **outdated** | Superseded by newer data |
    """)

    st.markdown("---")

    # Value Extraction
    st.header("5. Value Extraction Methodology")

    st.markdown("""
    **How numeric values are extracted from text:**

    ```
    Original Text: "$4.2B market size by 2025"
    ↓
    Regex: r'[\\d,]+\\.?\\d*' extracts first number
    ↓
    Numeric Value: 4.2
    ```

    **Limitations:**
    - Only the **first number** is extracted from text
    - For ranges like "12-18 months", only **12** is captured
    - Currency symbols and suffixes (B, M, K) are **not** factored into the numeric value
    - Always reference `value_text` for complete context

    **Best Practice:** When analyzing data, use:
    - `value` column for calculations and charts
    - `value_text` column for full context and units
    - `unit` from dimensions table for interpretation
    """)

    st.markdown("---")

    # Data Sources
    st.header("6. Source Types")

    source_query = """
        SELECT source_type, COUNT(*) as count
        FROM sources
        WHERE source_type IS NOT NULL
        GROUP BY source_type
        ORDER BY count DESC
    """
    source_df = run_query(source_query)

    if not source_df.empty:
        st.dataframe(source_df, hide_index=True)

    st.markdown("""
    **Source Reliability:**
    - Company filings and reports (high reliability)
    - Research firms (McKinsey, Gartner, IDC) (high reliability)
    - Industry associations (medium-high reliability)
    - News and press releases (medium reliability)
    - AI-generated estimates (requires validation)
    """)


elif page == "💬 AI Query Interface":
    st.title("AI Query Interface")
    st.markdown("Ask questions about the robotics database in natural language.")

    # Check AI backend status
    ai_backend = get_ai_backend()
    if not ai_backend:
        st.warning("**AI backend not configured.** Enter your OpenRouter API key below:")

        # API key input
        api_key_input = st.text_input(
            "OpenRouter API Key",
            type="password",
            placeholder="sk-or-v1-...",
            help="Get your key from https://openrouter.ai/keys"
        )

        if api_key_input:
            st.session_state.openrouter_key = api_key_input
            st.rerun()

        st.info("Your key is stored in session only (not saved permanently).")
        st.stop()
    else:
        st.success(f"✅ Using **{ai_backend.upper()}** backend")
        # Example queries
        st.markdown("### Example Questions")
        example_cols = st.columns(2)

        examples = [
            "What sector has the highest growth rate?",
            "Show me all high-confidence market size data",
            "List all data points for Industrial Robotics",
            "What are the top 5 sectors by market size?",
            "Show validation status breakdown by sector",
            "Which technologies are marked as emerging?"
        ]

        for i, example in enumerate(examples):
            col = example_cols[i % 2]
            if col.button(f"📝 {example}", key=f"example_{i}"):
                st.session_state.query_input = example

        st.markdown("---")

        # Query input
        query_input = st.text_area(
            "Enter your question:",
            value=st.session_state.get('query_input', ''),
            height=100,
            placeholder="e.g., What sector has the highest growth rate?"
        )

        col1, col2 = st.columns([1, 5])
        with col1:
            submit_button = st.button("🔍 Ask", type="primary")
        with col2:
            auto_execute = st.checkbox("Auto-execute SQL queries", value=True)

        if submit_button and query_input:
            with st.spinner("Thinking..."):
                # Get current data summary for context
                summary_query = """
                    SELECT
                        (SELECT COUNT(*) FROM data_points) as total_data_points,
                        (SELECT COUNT(*) FROM sectors) as total_sectors,
                        (SELECT COUNT(DISTINCT year) FROM data_points WHERE year IS NOT NULL) as years_covered
                """
                summary = run_query(summary_query).iloc[0]
                context = f"""
Current database contains:
- {summary['total_data_points']} data points
- {summary['total_sectors']} sectors
- Data from {summary['years_covered']} different years
"""

                # Query the LLM (use appropriate backend)
                if ai_backend == "ollama":
                    response = query_ollama(query_input, context)
                else:
                    response = query_openrouter(query_input, context)

                # Display response
                st.markdown("### Response")
                st.markdown(response)

                # Extract and optionally execute SQL
                sql_query = extract_sql_from_response(response)

                if sql_query and auto_execute:
                    st.markdown("### Query Results")
                    try:
                        # Validate it's a SELECT query (safety check)
                        if sql_query.strip().upper().startswith("SELECT"):
                            result_df = run_query(sql_query)
                            if not result_df.empty:
                                st.dataframe(result_df, width='stretch')

                                # Visualize if appropriate
                                if len(result_df.columns) >= 2 and len(result_df) > 1:
                                    numeric_cols = result_df.select_dtypes(include=['number']).columns.tolist()
                                    if numeric_cols:
                                        st.markdown("### Visualization")
                                        # Try to create a chart
                                        non_numeric = [c for c in result_df.columns if c not in numeric_cols]
                                        if non_numeric:
                                            x_col = non_numeric[0]
                                            y_col = numeric_cols[0]
                                            fig = px.bar(result_df, x=x_col, y=y_col)
                                            st.plotly_chart(fig, width='stretch')
                            else:
                                st.info("Query returned no results.")
                        else:
                            st.warning("Only SELECT queries are allowed for safety.")
                    except Exception as e:
                        st.error(f"Error executing query: {str(e)}")
                        st.code(sql_query, language="sql")
                elif sql_query:
                    st.markdown("### Generated SQL")
                    st.code(sql_query, language="sql")

        # Query history
        st.markdown("---")
        st.markdown("### Quick SQL Queries")

        quick_queries = {
            "Top sectors by data points": """
                SELECT s.name as sector, COUNT(*) as data_points
                FROM data_points dp
                JOIN sectors s ON dp.sector_id = s.id
                GROUP BY s.name
                ORDER BY data_points DESC
            """,
            "Growth rates by sector": """
                SELECT s.name as sector, dp.value as growth_rate, dp.year, dp.confidence
                FROM data_points dp
                JOIN sectors s ON dp.sector_id = s.id
                JOIN dimensions d ON dp.dimension_id = d.id
                WHERE d.name = 'market_growth_rate'
                ORDER BY dp.value DESC
            """,
            "High confidence data": """
                SELECT s.name as sector, d.name as dimension, dp.value, dp.year
                FROM data_points dp
                JOIN sectors s ON dp.sector_id = s.id
                JOIN dimensions d ON dp.dimension_id = d.id
                WHERE dp.confidence = 'high'
                ORDER BY dp.created_at DESC
                LIMIT 20
            """,
            "Market size summary": """
                SELECT s.name as sector,
                       dp.value as market_size_billions,
                       dp.year,
                       dp.confidence
                FROM data_points dp
                JOIN sectors s ON dp.sector_id = s.id
                JOIN dimensions d ON dp.dimension_id = d.id
                WHERE d.name = 'market_size'
                ORDER BY dp.value DESC
            """
        }

        selected_quick = st.selectbox("Select a quick query:", list(quick_queries.keys()))

        if st.button("▶️ Run Quick Query"):
            sql = quick_queries[selected_quick]
            st.code(sql, language="sql")
            try:
                result_df = run_query(sql)
                st.dataframe(result_df, width='stretch')
            except Exception as e:
                st.error(f"Error: {str(e)}")


# Footer
st.markdown("---")
st.caption("Robotics Intelligence Database | Powered by Streamlit & Ollama")
