"""
Data load only — assumes state column already exists.
Fetches all LEAs from NCES EDGE 2022-23 and populates the districts table.
"""

import time
import requests
from collections import Counter
from supabase import create_client

import os
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qvzwdcqshhajtpskqmxa.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_SECRET_KEY"]

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

# Child tables referencing districts — must be cleared first (FK order)
CHILD_TABLES = [
    ("intervention_assignments", "id"),
    ("observations", "id"),
    ("gap_profiles", "id"),
    ("caaspp_results", "district_id"),
    ("elpac_speaking", "district_id"),
    ("lcap_allocations", "district_id"),
]


def fetch_all_leas():
    all_records = []
    offset = 0
    while True:
        r = requests.get(EDGE_URL, params={
            "where": "1=1",
            "outFields": "LEAID,NAME,STATE,NMCNTY",
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "orderByFields": "OBJECTID",
        }, timeout=45)
        data = r.json()
        features = data.get("features", [])
        if not features:
            break
        all_records.extend(features)
        print(f"  Fetched {len(all_records):,}...", end="\r")
        if not data.get("exceededTransferLimit"):
            break
        offset += 2000
        time.sleep(0.15)
    print(f"  Fetched {len(all_records):,} total.     ")
    return all_records


def parse_leas(raw):
    leas = []
    for feat in raw:
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
        leas.append({
            "district_id": lea_id,
            "district_name": name,
            "county": county.strip(),
            "state": state,
        })
    return leas


def clear_table(client, table, pk):
    # Try integer sentinel, then UUID-safe approach (gt 0 epoch for uuid, or gte '')
    for sentinel in [("neq", "___x___"), ("gte", "00000000-0000-0000-0000-000000000000"), ("gte", "")]:
        op, val = sentinel
        try:
            getattr(client.table(table).delete(), op)(pk, val).execute()
            print(f"  Cleared {table}")
            return
        except Exception:
            continue
    # Last resort: fetch all IDs and delete in chunks
    try:
        rows = client.table(table).select(pk).execute().data
        ids = [r[pk] for r in rows]
        if not ids:
            print(f"  {table} already empty")
            return
        for i in range(0, len(ids), 200):
            chunk = ids[i:i+200]
            client.table(table).delete().in_(pk, chunk).execute()
        print(f"  Cleared {table} ({len(ids)} rows)")
    except Exception as e:
        print(f"  Skipped {table}: {e}")


def main():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Fetching LEA data from NCES EDGE 2022-23...")
    leas = parse_leas(fetch_all_leas())
    counts = Counter(d["state"] for d in leas)
    print(f"  {len(leas):,} valid LEAs across {len(counts)} jurisdictions")
    missing = [s for s in VALID_STATES if s not in counts]
    if missing:
        print(f"  WARNING missing: {missing}")

    print("\nClearing child tables (FK order)...")
    for table, pk in CHILD_TABLES:
        clear_table(client, table, pk)

    print("\nClearing districts...")
    try:
        client.table("districts").delete().neq("district_id", "___x___").execute()
        print("  Cleared districts")
    except Exception as e:
        print(f"  ERROR clearing districts: {e}")
        return

    print(f"\nInserting {len(leas):,} LEAs...")
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
                print("  Too many errors, stopping.")
                break
    print(f"\n  Inserted: {inserted:,}   Errors: {errors}")

    print("\nVerifying counts by state...")
    result = client.table("districts").select("state").execute()
    final = Counter(row.get("state") for row in result.data)
    for st in sorted(final):
        print(f"  {st}: {final[st]:,}")
    print(f"\nTotal: {sum(final.values()):,} districts")
    print("Done.")


if __name__ == "__main__":
    main()
