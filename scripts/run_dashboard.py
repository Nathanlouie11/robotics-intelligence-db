#!/usr/bin/env python3
"""
Streamlit Dashboard for Robotics Intelligence Database.

Run with: streamlit run scripts/run_dashboard.py
"""

import sys
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

# Page configuration
st.set_page_config(
    page_title="Robotics Intelligence Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Database connection
@st.cache_resource
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
- data_points: id, sector_id, subcategory_id, dimension_id, value, value_text,
               year, quarter, month, source_id, confidence, validation_status, notes
- technologies: id, name, category, description, maturity_level
- technology_data_points: id, technology_id, dimension_id, value, value_text, year, confidence

Key dimensions (metrics tracked):
- market_size (USD billions)
- market_growth_rate (percent)
- unit_shipments (units)
- average_selling_price (USD)
- deployment_count (units)
- adoption_rate (percent)
- funding_raised (USD millions)

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


# Sidebar
with st.sidebar:
    st.title("🤖 Robotics Intelligence")
    st.markdown("---")

    # Navigation
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "🔍 Data Explorer", "💬 AI Query Interface"],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Ollama status
    ollama_status = check_ollama_status()
    if ollama_status:
        st.success(f"✅ Ollama Connected")
        st.caption(f"Model: {OLLAMA_MODEL}")
    else:
        st.error("❌ Ollama Offline")
        st.caption(f"Expected at: {OLLAMA_HOST}")

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


elif page == "💬 AI Query Interface":
    st.title("AI Query Interface")
    st.markdown("Ask questions about the robotics database in natural language.")

    # Check Ollama status
    if not ollama_status:
        st.error(f"""
        **Ollama is not available** at {OLLAMA_HOST}

        Please make sure Ollama is running:
        1. Install Ollama from https://ollama.ai
        2. Run: `ollama serve`
        3. Pull the model: `ollama pull {OLLAMA_MODEL}`
        """)
    else:
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

                # Query the LLM
                response = query_ollama(query_input, context)

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
