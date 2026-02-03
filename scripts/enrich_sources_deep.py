"""
Deep Source Enrichment Script
Uses Kimi K2.5 to find actual source URLs and distinguish company types
"""

import sqlite3
import requests
import json
import re
import time
import os
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Configuration
DATABASE_PATH = Path(__file__).parent.parent / "data" / "robotics.db"
OPENROUTER_API_KEY = os.getenv('OPENROUTER_KEY')
MODEL = "google/gemini-2.0-flash-lite-001"  # Fast, reliable, cheap

def get_db_connection():
    return sqlite3.connect(DATABASE_PATH)

def get_api_key():
    """Get API key from environment or prompt user"""
    global OPENROUTER_API_KEY

    if OPENROUTER_API_KEY:
        return OPENROUTER_API_KEY

    # Check if key is in .env
    env_path = Path(__file__).parent.parent / ".env"

    # Prompt user for key
    print("\n[!] OpenRouter API key not found!")
    print("    Get your key from: https://openrouter.ai/keys")
    key = input("    Enter your OpenRouter API key: ").strip()

    if key:
        # Save to .env for future use
        with open(env_path, 'a') as f:
            f.write(f"\n# OpenRouter API Key for Kimi K2.5\nOPENROUTER_KEY={key}\n")
        print("    [OK] Key saved to .env file")
        OPENROUTER_API_KEY = key
        return key

    return None

def call_kimi_k2(prompt, max_tokens=2000):
    """Call Kimi K2.5 via OpenRouter API"""
    api_key = get_api_key()
    if not api_key:
        print("[ERROR] No API key available")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://robotics-intelligence-db.local",
        "X-Title": "Robotics Intelligence DB"
    }

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.HTTPError as e:
        if "401" in str(e):
            print(f"[ERROR] API key is invalid or expired. Please get a new key from https://openrouter.ai/keys")
        else:
            print(f"[ERROR] API call failed: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        return None

def get_data_points_needing_enrichment(limit=50):
    """Get data points that need source verification"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            dp.id,
            dp.value,
            dp.value_text,
            dp.year,
            dp.notes,
            dp.validation_status,
            dp.confidence,
            sec.name as sector,
            sub.name as subcategory,
            dim.name as dimension,
            dim.unit as dim_unit,
            src.id as source_id,
            src.name as source_name,
            src.url as source_url,
            src.source_type
        FROM data_points dp
        JOIN sectors sec ON dp.sector_id = sec.id
        LEFT JOIN subcategories sub ON dp.subcategory_id = sub.id
        JOIN dimensions dim ON dp.dimension_id = dim.id
        LEFT JOIN sources src ON dp.source_id = src.id
        WHERE (src.source_type = 'ai_generated' OR src.url IS NULL OR src.url = ''
               OR src.url NOT LIKE '%/%/%')
        ORDER BY dp.id
        LIMIT ?
    """

    cursor.execute(query, (limit,))
    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return results

def enrich_data_point(dp):
    """Use Kimi K2.5 to find actual sources and classify company type"""

    prompt = f"""You are a research analyst. Find the ACTUAL source URL for this robotics data.

DATA:
- Sector: {dp['sector']}
- Metric: {dp['dimension']} = {dp['value']} {dp['value_text'] or ''}
- Year: {dp['year']}
- Source: {dp['source_name']}
- Notes: {dp['notes'] or 'None'}

CLASSIFY:
- company_type: "startup" (founded after 2015, VC-funded) OR "established" (public/large corp) OR "research" (report/study)

FIND SOURCE URL:
- For public companies: SEC filings (sec.gov), investor relations pages
- For startups: Press releases, Crunchbase, TechCrunch
- For reports: Publisher website, PDF links

RESPOND WITH ONLY THIS JSON (no other text):
{{"company_type":"startup|established|research","company_name":"Name","primary_source":{{"name":"Source Title","url":"https://actual-url-or-null","excerpt":"where data appears"}},"secondary_sources":[],"verification_status":"VERIFIED|PARTIAL|UNVERIFIED","verification_notes":"explanation","suggested_notes":"context"}}"""

    response = call_kimi_k2(prompt, max_tokens=1000)
    if not response:
        return None

    # Parse JSON from response
    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except:
            pass

        # Try to extract JSON object from response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

    except json.JSONDecodeError as e:
        print(f"[WARNING] JSON parse error for ID {dp['id']}: {str(e)[:50]}")

    return None

def update_data_point_with_enrichment(dp_id, enrichment, source_id):
    """Update the database with enriched source information"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Update source with primary source info
        primary = enrichment.get('primary_source', {})
        primary_url = primary.get('url') if primary.get('url') else None

        # Build new source name with company context
        company_name = enrichment.get('company_name', '')
        company_type = enrichment.get('company_type', 'research')

        # Get current source name
        cursor.execute("SELECT name FROM sources WHERE id = ?", (source_id,))
        current_source = cursor.fetchone()
        current_name = current_source[0] if current_source else ""

        # Update source name to include company type marker
        if company_type == 'startup' and company_name and company_name != 'N/A':
            new_source_name = f"[STARTUP] {primary.get('name', current_name)}"
        elif company_type == 'established' and company_name and company_name != 'N/A':
            new_source_name = f"[{company_name}] {primary.get('name', current_name)}"
        else:
            new_source_name = primary.get('name', current_name)

        # Determine new source type
        verification = enrichment.get('verification_status', 'UNVERIFIED')
        if verification == 'VERIFIED':
            new_source_type = 'research_report'
            reliability = 0.85
        elif verification == 'PARTIAL':
            new_source_type = 'research_report'
            reliability = 0.65
        else:
            new_source_type = 'ai_generated'
            reliability = 0.4

        # Update source
        cursor.execute("""
            UPDATE sources
            SET name = ?, url = ?, source_type = ?, reliability_score = ?
            WHERE id = ?
        """, (new_source_name, primary_url, new_source_type, reliability, source_id))

        # Update data point notes with enriched information
        notes_parts = []

        if enrichment.get('suggested_notes'):
            notes_parts.append(enrichment['suggested_notes'])

        if enrichment.get('verification_notes'):
            notes_parts.append(f"[Verification: {verification}] {enrichment['verification_notes']}")

        # Add secondary sources to notes
        secondary = enrichment.get('secondary_sources', [])
        if secondary:
            sec_sources = "; ".join([f"{s.get('name', 'Unknown')}: {s.get('url', 'N/A')}" for s in secondary if s])
            notes_parts.append(f"[Additional Sources] {sec_sources}")

        # Mark if human verification needed
        if verification == 'UNVERIFIED':
            notes_parts.append("[REQUIRES HUMAN VERIFICATION]")

        new_notes = " | ".join(notes_parts) if notes_parts else None

        # Determine new confidence level
        if verification == 'VERIFIED':
            new_confidence = 'high'
        elif verification == 'PARTIAL':
            new_confidence = 'medium'
        else:
            new_confidence = 'low'

        cursor.execute("""
            UPDATE data_points
            SET notes = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_notes, new_confidence, dp_id))

        conn.commit()
        return True

    except Exception as e:
        print(f"[ERROR] Failed to update ID {dp_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def add_secondary_sources(dp_id, secondary_sources, primary_source_id):
    """Add secondary sources as additional source records linked to data point"""
    if not secondary_sources:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Note: Current schema links one source per data point
    # For now, we store secondary sources in notes
    # Future enhancement: Add data_point_sources junction table

    conn.close()

def run_enrichment(batch_size=20, delay_seconds=3, auto_confirm=False):
    """Run the enrichment process"""
    print("=" * 60)
    print("DEEP SOURCE ENRICHMENT")
    print("Finding actual source URLs and classifying companies")
    print("=" * 60)

    # Get data points needing enrichment
    data_points = get_data_points_needing_enrichment(batch_size)
    print(f"\n[INFO] Found {len(data_points)} data points needing enrichment")

    if not data_points:
        print("[INFO] No data points need enrichment!")
        return

    # Show preview
    print("\nData points to process:")
    for dp in data_points[:5]:
        print(f"  - ID {dp['id']}: {dp['sector']} > {dp['subcategory']} | {dp['dimension']} = {dp['value']}")
    if len(data_points) > 5:
        print(f"  ... and {len(data_points) - 5} more")

    if not auto_confirm:
        proceed = input("\nProceed with enrichment? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Cancelled.")
            return
    else:
        print("\n[AUTO] Proceeding with enrichment...")

    # Process each data point
    success_count = 0
    verified_count = 0
    partial_count = 0
    unverified_count = 0

    for i, dp in enumerate(data_points):
        print(f"\n[{i+1}/{len(data_points)}] Processing ID {dp['id']}: {dp['source_name'][:40]}...")

        # Get enrichment from Kimi K2.5
        enrichment = enrich_data_point(dp)

        if enrichment:
            status = enrichment.get('verification_status', 'UNVERIFIED')
            company_type = enrichment.get('company_type', 'unknown')
            primary_url = enrichment.get('primary_source', {}).get('url', 'None')

            print(f"    Company Type: {company_type}")
            print(f"    Verification: {status}")
            print(f"    Primary URL: {primary_url[:60] if primary_url else 'None'}...")

            # Update database
            if update_data_point_with_enrichment(dp['id'], enrichment, dp['source_id']):
                success_count += 1
                if status == 'VERIFIED':
                    verified_count += 1
                elif status == 'PARTIAL':
                    partial_count += 1
                else:
                    unverified_count += 1
                print(f"    [OK] Updated successfully")
            else:
                print(f"    [ERROR] Update failed")
        else:
            print(f"    [ERROR] No enrichment data returned")

        # Rate limiting
        if i < len(data_points) - 1:
            time.sleep(delay_seconds)

    # Summary
    print("\n" + "=" * 60)
    print("ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"Total processed: {len(data_points)}")
    print(f"Successfully updated: {success_count}")
    print(f"  - VERIFIED (exact source found): {verified_count}")
    print(f"  - PARTIAL (related source found): {partial_count}")
    print(f"  - UNVERIFIED (needs human review): {unverified_count}")

def show_enrichment_stats():
    """Show current enrichment statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("CURRENT ENRICHMENT STATUS")
    print("=" * 60)

    # Source types
    cursor.execute("""
        SELECT source_type, COUNT(*) as count,
               ROUND(AVG(reliability_score), 2) as avg_reliability
        FROM sources
        GROUP BY source_type
        ORDER BY count DESC
    """)
    print("\nSource Types:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} sources (avg reliability: {row[2]})")

    # Verification status in notes
    cursor.execute("""
        SELECT
            CASE
                WHEN notes LIKE '%REQUIRES HUMAN VERIFICATION%' THEN 'Needs Human Review'
                WHEN notes LIKE '%Verification: VERIFIED%' THEN 'Verified'
                WHEN notes LIKE '%Verification: PARTIAL%' THEN 'Partial'
                ELSE 'Not Enriched'
            END as status,
            COUNT(*) as count
        FROM data_points
        GROUP BY status
        ORDER BY count DESC
    """)
    print("\nData Point Verification Status:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} data points")

    # Company types (from source names)
    cursor.execute("""
        SELECT
            CASE
                WHEN name LIKE '[STARTUP]%' THEN 'Startup'
                WHEN name LIKE '[%]%' THEN 'Established Company'
                ELSE 'Research/Other'
            END as company_type,
            COUNT(*) as count
        FROM sources
        GROUP BY company_type
        ORDER BY count DESC
    """)
    print("\nCompany Types:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} sources")

    conn.close()

def main():
    import sys
    global OPENROUTER_API_KEY

    # Check for --key argument
    for i, arg in enumerate(sys.argv):
        if arg == '--key' and i + 1 < len(sys.argv):
            OPENROUTER_API_KEY = sys.argv[i + 1]
            print(f"[INFO] Using provided API key")

    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--enrich':
            # Parse batch size
            batch_size = 20
            for i, arg in enumerate(sys.argv):
                if arg.isdigit():
                    batch_size = int(arg)
                    break
            auto_confirm = '--yes' in sys.argv
            run_enrichment(batch_size=batch_size, auto_confirm=auto_confirm)
            return
        elif sys.argv[1] == '--stats':
            show_enrichment_stats()
            return
        elif sys.argv[1] == '--help':
            print("Usage:")
            print("  python enrich_sources_deep.py --enrich [batch_size] [--yes] [--key YOUR_KEY]")
            print("  python enrich_sources_deep.py --stats")
            print("  python enrich_sources_deep.py --key YOUR_KEY")
            print("\nSet OPENROUTER_KEY environment variable or add to .env file")
            return

    # Interactive mode
    print("\n" + "=" * 60)
    print("ROBOTICS INTELLIGENCE - DEEP SOURCE ENRICHMENT")
    print("=" * 60)
    print("\nOptions:")
    print("  1. Run enrichment (find actual source URLs)")
    print("  2. Show current enrichment stats")
    print("  3. Exit")

    choice = input("\nSelect option (1-3): ").strip()

    if choice == '1':
        batch = input("Batch size (default 20): ").strip()
        batch_size = int(batch) if batch.isdigit() else 20
        run_enrichment(batch_size=batch_size)
    elif choice == '2':
        show_enrichment_stats()
    else:
        print("Exiting.")

if __name__ == "__main__":
    main()
