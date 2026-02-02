#!/usr/bin/env python3
"""
Enrich robotics database with AI-inferred subcategories and source URLs.
Uses Kimi K2.5 via OpenRouter API.
"""

import os
import sqlite3
import json
import re
import time
from datetime import datetime
from openai import OpenAI

# Configuration
DB_PATH = r"C:\Users\nathan\robotics-intelligence-db\data\robotics.db"
API_KEY = os.getenv('OPENROUTER_KEY')

client = OpenAI(
    base_url='https://openrouter.ai/api/v1',
    api_key=API_KEY
)


def get_existing_subcategories(conn):
    """Get all existing subcategories grouped by sector."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.name as sector, sub.name as subcategory, sub.id
        FROM subcategories sub
        JOIN sectors s ON sub.sector_id = s.id
        ORDER BY s.name, sub.name
    ''')

    result = {}
    for sector, subcat, subcat_id in cursor.fetchall():
        if sector not in result:
            result[sector] = []
        result[sector].append({'name': subcat, 'id': subcat_id})

    return result


def get_data_points_needing_subcategory(conn):
    """Get data points that need subcategory assignment."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT dp.id, s.name as sector, d.name as dimension,
               dp.value, dp.value_text, dp.year, dp.notes,
               src.name as source_name
        FROM data_points dp
        JOIN sectors s ON dp.sector_id = s.id
        JOIN dimensions d ON dp.dimension_id = d.id
        LEFT JOIN sources src ON dp.source_id = src.id
        WHERE dp.subcategory_id IS NULL
        ORDER BY s.name, dp.id
    ''')
    return cursor.fetchall()


def get_sources_needing_urls(conn):
    """Get sources that need URL assignment."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, source_type
        FROM sources
        WHERE url IS NULL OR url = ''
        ORDER BY id
    ''')
    return cursor.fetchall()


def infer_subcategories_batch(data_points, existing_subcategories, sector):
    """Use AI to infer subcategories for a batch of data points."""

    # Get available subcategories for this sector
    available = existing_subcategories.get(sector, [])
    subcat_list = [s['name'] for s in available]

    # Build the prompt with clear IDs
    points_text = ""
    id_list = []
    for dp in data_points:
        dp_id, _, dimension, value, value_text, year, notes, source = dp
        val_display = value if value else value_text
        points_text += f"- DataPoint_{dp_id}: {dimension}, value={val_display}, source={source}\n"
        id_list.append(dp_id)

    prompt = f"""Categorize these {sector} data points into subcategories.

AVAILABLE SUBCATEGORIES:
{', '.join(subcat_list[:30])}

DATA POINTS TO CATEGORIZE:
{points_text}

For EACH data point, assign the best matching subcategory. Output ONLY a JSON array like this:
[{{"id": {id_list[0]}, "subcategory": "SubcategoryName"}}]

Include ALL {len(id_list)} data points. Use existing subcategories when possible.
If the data is general/sector-wide, use "General" or the main sector technology type.
Output valid JSON only, no explanation."""

    try:
        response = client.chat.completions.create(
            model='moonshotai/kimi-k2.5',
            messages=[
                {'role': 'system', 'content': 'You categorize robotics data. Return ONLY valid JSON arrays.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.2,
            max_tokens=3000
        )

        content = response.choices[0].message.content.strip()

        # Try to extract JSON
        # First try: direct parse
        try:
            return json.loads(content)
        except:
            pass

        # Second try: find array in content
        json_match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass

        # Third try: extract individual objects
        results = []
        for match in re.finditer(r'\{\s*"id"\s*:\s*(\d+)\s*,\s*"subcategory"\s*:\s*"([^"]+)"', content):
            results.append({"id": int(match.group(1)), "subcategory": match.group(2)})

        if results:
            return results

        print(f"  Could not parse response for {sector}")
        return []

    except Exception as e:
        print(f"Error inferring subcategories: {e}")
        return []


def find_source_urls_batch(sources):
    """Use AI to find URLs for sources."""

    sources_text = "\n".join([f"ID {s[0]}: {s[1]}" for s in sources])

    prompt = f"""
Find the official website URLs for these robotics industry sources/companies.

Sources:
{sources_text}

Return JSON array with the most likely official website URL for each:
[
  {{"id": 1, "url": "https://example.com", "confidence": "high"}},
  {{"id": 2, "url": "https://example.org", "confidence": "medium"}},
  {{"id": 3, "url": null, "confidence": "none"}},
  ...
]

Rules:
- Use official company/organization websites when possible
- For research reports, use the publisher's website
- For news sources, use the publication's website
- Set confidence: "high" (certain), "medium" (likely), "low" (guess), "none" (unknown)
- Return null for url if you cannot determine it
- Common robotics companies: Boston Dynamics (bostondynamics.com), ABB (abb.com), FANUC (fanuc.com), KUKA (kuka.com), etc.
- Research firms: McKinsey (mckinsey.com), Gartner (gartner.com), IDC (idc.com), etc.
"""

    try:
        response = client.chat.completions.create(
            model='moonshotai/kimi-k2.5',
            messages=[
                {'role': 'system', 'content': 'You are a research assistant finding official website URLs for companies and organizations.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.2,
            max_tokens=3000
        )

        content = response.choices[0].message.content

        # Extract JSON
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            return json.loads(json_match.group(0))

        return []
    except Exception as e:
        print(f"Error finding URLs: {e}")
        return []


def update_subcategory(conn, data_point_id, subcategory_name, sector_name):
    """Update a data point with its subcategory."""
    cursor = conn.cursor()

    # Get sector_id
    cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_name,))
    sector_row = cursor.fetchone()
    if not sector_row:
        return False
    sector_id = sector_row[0]

    # Get or create subcategory
    cursor.execute(
        "SELECT id FROM subcategories WHERE name = ? AND sector_id = ?",
        (subcategory_name, sector_id)
    )
    row = cursor.fetchone()

    if row:
        subcategory_id = row[0]
    else:
        # Create new subcategory
        cursor.execute(
            "INSERT INTO subcategories (name, sector_id, created_at) VALUES (?, ?, ?)",
            (subcategory_name, sector_id, datetime.now().isoformat())
        )
        subcategory_id = cursor.lastrowid
        print(f"  Created new subcategory: {subcategory_name}")

    # Update data point
    cursor.execute(
        "UPDATE data_points SET subcategory_id = ? WHERE id = ?",
        (subcategory_id, data_point_id)
    )

    return True


def update_source_url(conn, source_id, url):
    """Update a source with its URL."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sources SET url = ? WHERE id = ?",
        (url, source_id)
    )
    return True


def main():
    if not API_KEY:
        print("ERROR: OPENROUTER_KEY not set")
        return

    conn = sqlite3.connect(DB_PATH)

    print("=" * 60)
    print("ROBOTICS DATABASE ENRICHMENT")
    print("=" * 60)

    # Get existing subcategories
    existing_subcategories = get_existing_subcategories(conn)

    # === PHASE 1: Fill missing subcategories ===
    print("\n[PHASE 1] Filling missing subcategories...")

    data_points = get_data_points_needing_subcategory(conn)
    print(f"Found {len(data_points)} data points needing subcategories")

    if data_points:
        # Group by sector
        by_sector = {}
        for dp in data_points:
            sector = dp[1]
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(dp)

        total_updated = 0

        for sector, points in by_sector.items():
            print(f"\nProcessing {sector} ({len(points)} points)...")

            # Process in batches of 20
            batch_size = 20
            for i in range(0, len(points), batch_size):
                batch = points[i:i+batch_size]

                results = infer_subcategories_batch(batch, existing_subcategories, sector)

                for result in results:
                    dp_id = result.get('id')
                    subcat = result.get('subcategory')

                    if dp_id and subcat:
                        if update_subcategory(conn, dp_id, subcat, sector):
                            total_updated += 1

                # Rate limiting
                time.sleep(1)

            conn.commit()

        print(f"\n[OK] Updated {total_updated} data points with subcategories")

    # === PHASE 2: Fill missing source URLs ===
    print("\n[PHASE 2] Finding missing source URLs...")

    sources = get_sources_needing_urls(conn)
    print(f"Found {len(sources)} sources needing URLs")

    if sources:
        total_urls_added = 0

        # Process in batches of 25
        batch_size = 25
        for i in range(0, len(sources), batch_size):
            batch = sources[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(sources)-1)//batch_size + 1}...")

            results = find_source_urls_batch(batch)

            for result in results:
                source_id = result.get('id')
                url = result.get('url')
                confidence = result.get('confidence', 'low')

                if source_id and url and confidence in ['high', 'medium']:
                    if update_source_url(conn, source_id, url):
                        total_urls_added += 1

            conn.commit()
            time.sleep(1)

        print(f"\n[OK] Added URLs to {total_urls_added} sources")

    conn.close()

    print("\n" + "=" * 60)
    print("ENRICHMENT COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
