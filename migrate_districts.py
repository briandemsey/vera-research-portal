"""
One-time migration: populate districts table from NCES EDGE API (all 50 states + DC).
- Adds state column via direct postgres
- Clears child tables (caaspp_results, elpac_speaking, gap_profiles, etc.) then districts
- Inserts all ~19,700 LEAs from NCES EDGE 2022-23
"""

import time
import requests
from supabase import create_client

import os
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qvzwdcqshhajtpskqmxa.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]
PROJECT_REF  = "qvzwdcqshhajtpskqmxa"

EDGE_URL = (
    "https://nces.ed.gov/opengis/rest/services"
    "/K12_School_Locations/EDGE_GEOCODE_PUBLICLEA_2223/MapServer/0/query"
)

VALID_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH",
    "NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT",
    "VT","VA","WA","WV","WI","WY",
}

# Tables that reference districts via FK (delete these first)
CHILD_TABLES = [
    "intervention_assignments",  # references gap_profiles
    "observations",              # references gap_profiles
    "gap_profiles",              # references districts
    "caaspp_results",            # references districts
    "elpac_speaking",            # references districts
    "lcap_allocations",          # references districts
]


def try_postgres_ddl():
    """Try adding state column via direct postgres connection."""
    try:
        import psycopg2
        # Supabase postgres connection — project ref as username prefix
        # Format: postgres.[project-ref]@aws-0-<region>.pooler.supabase.com:5432
        conn_str = (
            f"postgresql://postgres.{PROJECT_REF}:{SUPABASE_KEY}"
            f"@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
        )
        conn = psycopg2.connect(conn_str, connect_timeout=15)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("ALTER TABLE districts ADD COLUMN IF NOT EXISTS state TEXT")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_districts_state ON districts(state)")
        conn.close()
        return True, "via direct postgres (port 5432)"
    except Exception as e:
        pass

    # Try session pooler port 6543
    try:
        import psycopg2
        conn_str = (
            f"postgresql://postgres.{PROJECT_REF}:{SUPABASE_KEY}"
            f"@aws-0-us-east-2.pooler.supabase.com:6543/postgres"
        )
        conn = psycopg2.connect(conn_str, connect_timeout=15)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("ALTER TABLE districts ADD COLUMN IF NOT EXISTS state TEXT")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_districts_state ON districts(state)")
        conn.close()
        return True, "via pooler (us-east-2)"
    except Exception as e:
        return False, str(e)


def fetch_all_leas() -> list[dict]:
    """Page through all LEAs from NCES EDGE MapServer."""
    all_records = []
    offset = 0
    page_size = 2000

    while True:
        params = {
            "where": "1=1",
            "outFields": "LEAID,NAME,STATE,NMCNTY",
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "orderByFields": "OBJECTID",
        }
        try:
            r = requests.get(EDGE_URL, params=params, timeout=45)
            data = r.json()
        except Exception as e:
            print(f"\n  Fetch error at offset {offset}: {e}")
            break

        features = data.get("features", [])
        if not features:
            break

        all_records.extend(features)
        print(f"  Fetched {len(all_records):,} LEAs...", end="\r")

        if not data.get("exceededTransferLimit", False):
            break

        offset += page_size
        time.sleep(0.15)

    print(f"  Fetched {len(all_records):,} LEAs total.     ")
    return all_records


def parse_leas(raw_features: list) -> list[dict]:
    leas = []
    for feat in raw_features:
        a = feat.get("attributes", {})
        lea_id = str(a.get("LEAID") or "").strip()
        name   = str(a.get("NAME") or "").strip()
        state  = str(a.get("STATE") or "").strip().upper()
        county = str(a.get("NMCNTY") or "").strip()

        if not lea_id or not name or state not in VALID_STATES:
            continue

        for suffix in [" County", " Parish", " Borough", " Census Area",
                       " Municipality", " City and Borough"]:
            county = county.replace(suffix, "")
        county = county.strip()

        leas.append({
            "district_id": lea_id,
            "district_name": name,
            "county": county,
            "state": state,
        })
    return leas


def delete_all_rows(client, table: str):
    """Delete all rows from a table using a dummy neq filter."""
    try:
        client.table(table).delete().neq("id", -999999).execute()
        return True
    except Exception:
        pass
    try:
        # Some tables use different PK names
        client.table(table).delete().neq("district_id", "___x___").execute()
        return True
    except Exception as e:
        print(f"    Could not clear {table}: {e}")
        return False


def migrate():
    print(f"Connecting to Supabase: {SUPABASE_URL}\n")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Step 1: Add state column
    print("Step 1: Adding state column...")
    ok, msg = try_postgres_ddl()
    if ok:
        print(f"  State column added {msg}.")
    else:
        print(f"  Automatic DDL failed: {msg}")
        print("\n  ACTION REQUIRED: Run this SQL in the Supabase dashboard SQL editor:")
        print("  https://supabase.com/dashboard/project/qvzwdcqshhajtpskqmxa/sql")
        print()
        print("    ALTER TABLE districts ADD COLUMN IF NOT EXISTS state TEXT;")
        print("    CREATE INDEX IF NOT EXISTS idx_districts_state ON districts(state);")
        print()
        input("  Press Enter once you've run the SQL, then we'll continue...")

    # Step 2: Fetch NCES data
    print("\nStep 2: Fetching LEA data from NCES EDGE 2022-23...")
    raw = fetch_all_leas()
    leas = parse_leas(raw)
    print(f"  Valid LEAs: {len(leas):,}")

    from collections import Counter
    state_counts = Counter(d["state"] for d in leas)
    missing = [s for s in VALID_STATES if s not in state_counts]
    if missing:
        print(f"  WARNING — no LEAs for: {missing}")
    else:
        print(f"  All {len(VALID_STATES)} jurisdictions covered.")

    # Step 3: Clear child tables first (FK order), then districts
    print("\nStep 3: Clearing existing data (FK-safe order)...")
    for table in CHILD_TABLES:
        print(f"  Clearing {table}...", end=" ")
        delete_all_rows(client, table)
        print("done")

    print("  Clearing districts...", end=" ")
    try:
        client.table("districts").delete().neq("district_id", "___x___").execute()
        print("done")
    except Exception as e:
        print(f"ERROR: {e}")
        return

    # Step 4: Batch insert
    print(f"\nStep 4: Inserting {len(leas):,} LEAs (batch 500)...")
    batch_size = 500
    inserted = 0
    errors = 0
    for i in range(0, len(leas), batch_size):
        batch = leas[i:i + batch_size]
        try:
            client.table("districts").insert(batch).execute()
            inserted += len(batch)
            print(f"  {inserted:,} / {len(leas):,}", end="\r")
        except Exception as e:
            errors += 1
            print(f"\n  ERROR batch {i}: {e}")
            if errors > 5:
                print("  Too many errors — stopping.")
                break
    print(f"\n  Inserted: {inserted:,}   Errors: {errors}")

    # Step 5: Verify
    print("\nStep 5: Counts by state...")
    result = client.table("districts").select("state").execute()
    counts = Counter(row.get("state") for row in result.data)
    for st in sorted(counts):
        print(f"  {st}: {counts[st]:,}")
    print(f"\n  Total: {sum(counts.values()):,} districts")
    print("\nMigration complete.")


if __name__ == "__main__":
    migrate()
