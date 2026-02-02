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
        ["📊 Dashboard", "🔍 Data Explorer", "📑 Technical Intelligence", "✅ Validation", "📋 Methodology", "💬 AI Query Interface"],
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

        # Build query
        dp_query = """
            SELECT
                dp.id,
                s.name as sector,
                sub.name as subcategory,
                d.name as dimension,
                dp.value,
                dp.value_text,
                dp.year,
                dp.confidence,
                dp.validation_status,
                src.name as source,
                src.url as source_url,
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

        st.markdown(f"**{len(dp_df)} data points** matching filters")

        if not dp_df.empty:
            # Display with validation controls
            for idx, row in dp_df.iterrows():
                with st.expander(f"ID {row['id']}: {row['sector']} > {row['subcategory'] or 'N/A'} | {row['dimension']} = {row['value_text'] or row['value']}"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown(f"""
                        **Sector:** {row['sector']}
                        **Subcategory:** {row['subcategory'] or 'N/A'}
                        **Dimension:** {row['dimension']}
                        **Value:** {row['value']} ({row['value_text'] or 'N/A'})
                        **Year:** {row['year']}
                        **Source:** {row['source']}
                        **Notes:** {row['notes'] or 'N/A'}
                        """)

                        if row['source_url']:
                            st.markdown(f"🔗 [Verify Source]({row['source_url']})")

                    with col2:
                        new_status = st.selectbox(
                            "Status",
                            ["pending", "in_review", "validated", "rejected", "outdated"],
                            index=["pending", "in_review", "validated", "rejected", "outdated"].index(row['validation_status']) if row['validation_status'] in ["pending", "in_review", "validated", "rejected", "outdated"] else 0,
                            key=f"status_{row['id']}"
                        )

                        new_conf = st.selectbox(
                            "Confidence",
                            ["high", "medium", "low", "unverified"],
                            index=["high", "medium", "low", "unverified"].index(row['confidence']) if row['confidence'] in ["high", "medium", "low", "unverified"] else 1,
                            key=f"conf_{row['id']}"
                        )

                        if st.button("💾 Save", key=f"save_{row['id']}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE data_points
                                SET validation_status = ?, confidence = ?, validated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (new_status, new_conf, row['id']))
                            conn.commit()
                            st.success(f"Updated ID {row['id']}")
                            st.rerun()

    with val_tab2:
        st.subheader("Validate Sources")

        # Source type filter
        source_type_filter = st.selectbox(
            "Source Type",
            ["ai_generated", "All", "research_report", "news", "company", "government"],
            key="src_type"
        )

        # Build source query
        src_query = """
            SELECT
                id,
                name,
                url,
                source_type,
                reliability_score,
                (SELECT COUNT(*) FROM data_points WHERE source_id = sources.id) as data_point_count
            FROM sources
            WHERE 1=1
        """
        src_params = []

        if source_type_filter != "All":
            src_query += " AND source_type = ?"
            src_params.append(source_type_filter)

        src_query += " ORDER BY id DESC LIMIT 50"

        src_df = run_query(src_query, tuple(src_params))

        st.markdown(f"**{len(src_df)} sources** matching filters")

        if not src_df.empty:
            for idx, row in src_df.iterrows():
                with st.expander(f"ID {row['id']}: {row['name'][:60]}... ({row['data_point_count']} data points)"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown(f"**Name:** {row['name']}")
                        st.markdown(f"**Current Type:** {row['source_type']}")
                        st.markdown(f"**Reliability Score:** {row['reliability_score']}")
                        st.markdown(f"**Data Points Using:** {row['data_point_count']}")

                        if row['url']:
                            st.markdown(f"🔗 [Visit Source]({row['url']})")
                        else:
                            st.warning("No URL set")

                    with col2:
                        new_url = st.text_input(
                            "URL",
                            value=row['url'] or "",
                            key=f"url_{row['id']}"
                        )

                        new_type = st.selectbox(
                            "Type",
                            ["ai_generated", "research_report", "news", "company", "government", "academic"],
                            index=["ai_generated", "research_report", "news", "company", "government", "academic"].index(row['source_type']) if row['source_type'] in ["ai_generated", "research_report", "news", "company", "government", "academic"] else 0,
                            key=f"type_{row['id']}"
                        )

                        new_reliability = st.slider(
                            "Reliability",
                            0.0, 1.0,
                            value=float(row['reliability_score']) if row['reliability_score'] else 0.5,
                            step=0.1,
                            key=f"rel_{row['id']}"
                        )

                        if st.button("💾 Save", key=f"save_src_{row['id']}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE sources
                                SET url = ?, source_type = ?, reliability_score = ?
                                WHERE id = ?
                            """, (new_url, new_type, new_reliability, row['id']))
                            conn.commit()
                            st.success(f"Updated source ID {row['id']}")
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
