"""
Data Refresh Script for Robotics Intelligence Database

Fetches and updates:
- Funding announcements
- Partnership news
- Case studies
- Industry pain points
- Adoption signals

Uses AI to extract structured data from news and reports.
"""

import sqlite3
import requests
import json
import re
import os
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
DATABASE_PATH = Path(__file__).parent.parent / "data" / "robotics.db"

# Load API keys from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY')
MODEL = "google/gemini-2.0-flash-lite-001"

def get_connection():
    return sqlite3.connect(DATABASE_PATH)

def call_ai(prompt, max_tokens=2000):
    """Call AI model for data extraction."""
    if not OPENROUTER_KEY:
        print("[ERROR] OPENROUTER_KEY not set")
        return None

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"[ERROR] AI call failed: {e}")
        return None

def search_web(query, count=10):
    """Search web using Brave Search API."""
    if not BRAVE_API_KEY:
        print("[WARNING] BRAVE_API_KEY not set, skipping web search")
        return []

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": count},
            timeout=30
        )
        response.raise_for_status()
        results = response.json().get('web', {}).get('results', [])
        return [{'title': r['title'], 'url': r['url'], 'description': r.get('description', '')} for r in results]
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return []

def log_refresh(refresh_type, status, records_added=0, records_updated=0, errors=None):
    """Log refresh activity."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO data_refresh_log (refresh_type, started_at, completed_at, records_added, records_updated, errors, status)
        VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?)
    """, (refresh_type, records_added, records_updated, errors, status))
    conn.commit()
    conn.close()

def get_or_create_company(cursor, name, company_type='startup'):
    """Get or create a company record."""
    cursor.execute("SELECT id FROM companies WHERE name = ?", (name,))
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute("""
        INSERT INTO companies (name, company_type, status)
        VALUES (?, ?, 'active')
    """, (name, company_type))
    return cursor.lastrowid

def refresh_funding():
    """Fetch and update funding announcements."""
    print("\n" + "="*60)
    print("REFRESHING FUNDING DATA")
    print("="*60)

    # Search for recent robotics funding news
    searches = [
        "robotics startup funding 2025",
        "robot company series funding round 2025",
        "humanoid robot investment 2025",
        "warehouse automation funding 2025",
        "AI robotics venture capital 2025",
    ]

    all_results = []
    for query in searches:
        print(f"  Searching: {query}")
        results = search_web(query, count=5)
        all_results.extend(results)

    if not all_results:
        print("[WARNING] No search results found")
        return

    # Remove duplicates by URL
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r['url'] not in seen_urls:
            seen_urls.add(r['url'])
            unique_results.append(r)

    print(f"\nFound {len(unique_results)} unique articles")

    # Use AI to extract funding data from search results
    articles_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\nDescription: {r['description']}"
        for r in unique_results[:15]
    ])

    prompt = f"""Extract robotics funding announcements from these search results.

SEARCH RESULTS:
{articles_text}

For each funding announcement, extract:
- company_name: Company that received funding
- amount_millions: Amount in USD millions (e.g., 675 for $675M)
- round_type: seed, series_a, series_b, series_c, series_d, growth, or unknown
- announced_date: Date in YYYY-MM-DD format (estimate if not exact)
- lead_investors: Main investors (comma-separated)
- valuation_millions: Post-money valuation if mentioned
- source_url: URL of the article

Return ONLY a JSON array of funding objects. No other text.
Example: [{{"company_name":"Figure AI","amount_millions":675,"round_type":"series_b","announced_date":"2024-02-29","lead_investors":"Microsoft, OpenAI","valuation_millions":2600,"source_url":"https://..."}}]

If no funding announcements found, return empty array: []"""

    response = call_ai(prompt, max_tokens=3000)
    if not response:
        return

    # Parse response
    try:
        # Clean response
        cleaned = response.strip()
        if '```' in cleaned:
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```', '', cleaned)

        funding_data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse AI response: {e}")
        print(f"Response: {response[:500]}")
        return

    if not funding_data:
        print("No new funding announcements found")
        return

    print(f"\nExtracted {len(funding_data)} funding announcements")

    # Insert into database
    conn = get_connection()
    cursor = conn.cursor()
    added = 0

    for f in funding_data:
        try:
            company_name = f.get('company_name', '').strip()
            if not company_name or len(company_name) < 2:
                continue

            amount = f.get('amount_millions')
            if not amount:
                continue

            # Get or create company
            company_id = get_or_create_company(cursor, company_name)

            # Check for duplicate
            round_type = f.get('round_type', 'unknown')
            cursor.execute("""
                SELECT id FROM funding_rounds
                WHERE company_id = ? AND amount_millions = ? AND round_type = ?
            """, (company_id, amount, round_type))

            if cursor.fetchone():
                print(f"  [SKIP] {company_name} ${amount}M (duplicate)")
                continue

            # Create source
            source_url = f.get('source_url', '')
            cursor.execute("""
                INSERT INTO sources (name, url, source_type, reliability_score)
                VALUES (?, ?, 'news', 0.7)
            """, (f"[STARTUP] {company_name} funding announcement", source_url))
            source_id = cursor.lastrowid

            # Insert funding round
            cursor.execute("""
                INSERT INTO funding_rounds
                (company_id, round_type, amount_millions, announced_date, lead_investors, post_money_valuation_millions, source_id, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_id,
                round_type,
                amount,
                f.get('announced_date'),
                f.get('lead_investors'),
                f.get('valuation_millions'),
                source_id,
                source_url
            ))

            print(f"  [ADD] {company_name}: ${amount}M {round_type}")
            added += 1

        except Exception as e:
            print(f"  [ERROR] {e}")

    # Update company totals
    cursor.execute("""
        UPDATE companies SET total_funding_millions = (
            SELECT SUM(amount_millions) FROM funding_rounds WHERE funding_rounds.company_id = companies.id
        )
    """)

    conn.commit()
    conn.close()

    log_refresh('funding', 'completed', records_added=added)
    print(f"\nAdded {added} new funding rounds")

def refresh_partnerships():
    """Fetch and update partnership announcements."""
    print("\n" + "="*60)
    print("REFRESHING PARTNERSHIP DATA")
    print("="*60)

    searches = [
        "robotics company partnership announcement 2025",
        "robot manufacturer partnership deal 2025",
        "automation company strategic partnership 2025",
    ]

    all_results = []
    for query in searches:
        print(f"  Searching: {query}")
        results = search_web(query, count=5)
        all_results.extend(results)

    if not all_results:
        print("[WARNING] No search results found")
        return

    # Remove duplicates
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r['url'] not in seen_urls:
            seen_urls.add(r['url'])
            unique_results.append(r)

    print(f"\nFound {len(unique_results)} unique articles")

    articles_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\nDescription: {r['description']}"
        for r in unique_results[:10]
    ])

    prompt = f"""Extract robotics partnership announcements from these search results.

SEARCH RESULTS:
{articles_text}

For each partnership, extract:
- company1_name: First company (robotics company)
- company2_name: Partner company
- partnership_type: integration, distribution, manufacturing, research, investment, customer, or other
- announcement_date: Date in YYYY-MM-DD format
- title: Brief title of the partnership
- description: What the partnership involves
- source_url: URL of the article

Return ONLY a JSON array. No other text.
Example: [{{"company1_name":"Boston Dynamics","company2_name":"Hyundai","partnership_type":"investment","announcement_date":"2024-01-15","title":"Hyundai invests in Boston Dynamics","description":"...","source_url":"https://..."}}]

If no partnerships found, return: []"""

    response = call_ai(prompt, max_tokens=2000)
    if not response:
        return

    try:
        cleaned = response.strip()
        if '```' in cleaned:
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```', '', cleaned)
        partnerships = json.loads(cleaned)
    except json.JSONDecodeError:
        print("[ERROR] Failed to parse response")
        return

    if not partnerships:
        print("No new partnerships found")
        return

    print(f"\nExtracted {len(partnerships)} partnerships")

    conn = get_connection()
    cursor = conn.cursor()
    added = 0

    for p in partnerships:
        try:
            c1_name = p.get('company1_name', '').strip()
            c2_name = p.get('company2_name', '').strip()
            if not c1_name or not c2_name:
                continue

            c1_id = get_or_create_company(cursor, c1_name)

            # Check for duplicate
            cursor.execute("""
                SELECT id FROM partnerships
                WHERE company1_id = ? AND company2_name = ? AND title = ?
            """, (c1_id, c2_name, p.get('title', '')))

            if cursor.fetchone():
                print(f"  [SKIP] {c1_name} + {c2_name} (duplicate)")
                continue

            cursor.execute("""
                INSERT INTO partnerships
                (company1_id, company2_name, partnership_type, announcement_date, title, description, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                c1_id,
                c2_name,
                p.get('partnership_type', 'other'),
                p.get('announcement_date'),
                p.get('title'),
                p.get('description'),
                p.get('source_url')
            ))

            print(f"  [ADD] {c1_name} + {c2_name}")
            added += 1

        except Exception as e:
            print(f"  [ERROR] {e}")

    conn.commit()
    conn.close()

    log_refresh('partnerships', 'completed', records_added=added)
    print(f"\nAdded {added} new partnerships")

def refresh_pain_points():
    """Identify and track industry pain points."""
    print("\n" + "="*60)
    print("REFRESHING PAIN POINTS DATA")
    print("="*60)

    searches = [
        "robotics industry challenges 2025",
        "robot adoption barriers enterprise",
        "warehouse automation problems",
        "humanoid robot limitations",
        "industrial robot integration challenges",
    ]

    all_results = []
    for query in searches:
        print(f"  Searching: {query}")
        results = search_web(query, count=5)
        all_results.extend(results)

    if not all_results:
        print("[WARNING] No search results found")
        return

    articles_text = "\n\n".join([
        f"Title: {r['title']}\nDescription: {r['description']}"
        for r in all_results[:15]
    ])

    prompt = f"""Identify robotics industry pain points from these sources.

SOURCES:
{articles_text}

For each pain point, extract:
- title: Brief title (e.g., "High integration costs")
- category: technical, cost, integration, workforce, regulatory, safety, scalability, reliability, or other
- scale: startup, smb, mid_market, enterprise, or industry_wide
- description: Detailed description of the challenge
- severity: critical, high, medium, or low
- potential_solutions: Known solutions or approaches

Return ONLY a JSON array. No other text.
Example: [{{"title":"High integration costs","category":"cost","scale":"enterprise","description":"...","severity":"high","potential_solutions":"..."}}]"""

    response = call_ai(prompt, max_tokens=2000)
    if not response:
        return

    try:
        cleaned = response.strip()
        if '```' in cleaned:
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```', '', cleaned)
        pain_points = json.loads(cleaned)
    except json.JSONDecodeError:
        print("[ERROR] Failed to parse response")
        return

    print(f"\nExtracted {len(pain_points)} pain points")

    conn = get_connection()
    cursor = conn.cursor()
    added = 0

    for pp in pain_points:
        try:
            title = pp.get('title', '').strip()
            if not title:
                continue

            # Check for similar existing pain point
            cursor.execute("SELECT id, frequency_mentioned FROM pain_points WHERE title LIKE ?", (f"%{title[:20]}%",))
            existing = cursor.fetchone()

            if existing:
                # Update frequency
                cursor.execute("UPDATE pain_points SET frequency_mentioned = ?, last_mentioned_date = DATE('now') WHERE id = ?",
                             (existing[1] + 1, existing[0]))
                print(f"  [UPDATE] {title[:40]} (freq: {existing[1] + 1})")
            else:
                cursor.execute("""
                    INSERT INTO pain_points
                    (title, category, scale, description, severity, potential_solutions, first_identified_date, last_mentioned_date)
                    VALUES (?, ?, ?, ?, ?, ?, DATE('now'), DATE('now'))
                """, (
                    title,
                    pp.get('category', 'other'),
                    pp.get('scale', 'industry_wide'),
                    pp.get('description'),
                    pp.get('severity', 'medium'),
                    pp.get('potential_solutions')
                ))
                print(f"  [ADD] {title[:40]}")
                added += 1

        except Exception as e:
            print(f"  [ERROR] {e}")

    conn.commit()
    conn.close()

    log_refresh('pain_points', 'completed', records_added=added)
    print(f"\nAdded {added} new pain points")

def show_refresh_status():
    """Show current data status and refresh history."""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("DATA REFRESH STATUS")
    print("="*60)

    # Table counts
    tables = [
        ('companies', 'Companies tracked'),
        ('funding_rounds', 'Funding rounds'),
        ('partnerships', 'Partnerships'),
        ('case_studies', 'Case studies'),
        ('pain_points', 'Pain points'),
        ('adoption_signals', 'Adoption signals'),
    ]

    print("\nCurrent data:")
    for table, desc in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {desc:25} {count:>6}")

    # Recent refreshes
    print("\nRecent refreshes:")
    cursor.execute("""
        SELECT refresh_type, completed_at, records_added, status
        FROM data_refresh_log
        ORDER BY completed_at DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]:15} | {row[1]} | +{row[2]} | {row[3]}")

    conn.close()

def main():
    import sys

    print("="*60)
    print("ROBOTICS INTELLIGENCE - DATA REFRESH")
    print("="*60)

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--funding':
            refresh_funding()
        elif arg == '--partnerships':
            refresh_partnerships()
        elif arg == '--pain-points':
            refresh_pain_points()
        elif arg == '--all':
            refresh_funding()
            refresh_partnerships()
            refresh_pain_points()
        elif arg == '--status':
            show_refresh_status()
        else:
            print(f"Unknown argument: {arg}")
            print("\nUsage:")
            print("  python refresh_data.py --funding      Refresh funding data")
            print("  python refresh_data.py --partnerships Refresh partnership data")
            print("  python refresh_data.py --pain-points  Refresh pain points")
            print("  python refresh_data.py --all          Refresh all data")
            print("  python refresh_data.py --status       Show refresh status")
    else:
        print("\nOptions:")
        print("  1. Refresh funding data")
        print("  2. Refresh partnerships")
        print("  3. Refresh pain points")
        print("  4. Refresh all")
        print("  5. Show status")
        print("  6. Exit")

        choice = input("\nSelect (1-6): ").strip()

        if choice == '1':
            refresh_funding()
        elif choice == '2':
            refresh_partnerships()
        elif choice == '3':
            refresh_pain_points()
        elif choice == '4':
            refresh_funding()
            refresh_partnerships()
            refresh_pain_points()
        elif choice == '5':
            show_refresh_status()
        else:
            print("Exiting.")

if __name__ == "__main__":
    main()
