# VERA Research Portal — Working Guide
## Expanding to All Jurisdictions

This guide documents what was built, how the system works end-to-end,
and how to maintain or extend it going forward.

---

## What Was Built

The VERA Research Portal (`jeremy.h-edu.solutions`) was expanded from
California-only to all 50 US states + DC.

**Changes made:**

| Component | What changed |
|---|---|
| `main.py` | Added `JURISDICTIONS` dict with assessment names per state; new `/api/jurisdictions` endpoint; `/api/districts` now accepts `?state=XX` filter; AI chat prompt resolves state-specific assessment terminology |
| `static/index.html` | Jurisdiction dropdown added to sidebar; district list lazy-loads on state selection; tab labels and empty states use state-correct assessment names; chat passes state to AI |
| Supabase `districts` table | Added `state TEXT` column + index; replaced CA-only data with 19,704 LEAs across all 51 jurisdictions |

---

## Architecture

```
Browser → jeremy.h-edu.solutions
            ↓
         Render.com (vera-research-portal service)
            ↓
         FastAPI (main.py)
            ├── Static files → static/index.html
            ├── /api/jurisdictions → hardcoded JURISDICTIONS dict
            ├── /api/districts?state=XX → Supabase: districts table
            ├── /api/districts/{id}/gaps → Supabase: gap_profiles
            ├── /api/districts/{id}/caaspp → Supabase: caaspp_results
            ├── /api/districts/{id}/elpac → Supabase: elpac_speaking
            ├── /api/districts/{id}/lcap → Supabase: lcap_allocations
            └── /api/chat → Anthropic Claude API
```

**GitHub repo:** github.com/briandemsey/vera-research-portal
**Supabase project:** qvzwdcqshhajtpskqmxa
**Deploy:** Push to GitHub → Render auto-deploys in ~2 minutes

---

## Database: Supabase

**Project:** qvzwdcqshhajtpskqmxa
**Dashboard:** supabase.com/dashboard/project/qvzwdcqshhajtpskqmxa

### districts table

The master LEA list. Source: NCES EDGE GEOCODE PUBLICLEA 2022-23.

| Column | Type | Notes |
|---|---|---|
| district_id | TEXT | NCES LEAID (7-digit) |
| district_name | TEXT | Official LEA name |
| county | TEXT | County/parish name (suffix stripped) |
| state | TEXT | 2-char state abbreviation |

**Row counts (as of migration):** 19,704 total
- CA: 2,147 · TX: 1,240 · NY: 1,112 · OH: 1,058 · IL: 1,035
- HI: 1 (single statewide DOE — correct)

### Other tables (assessment data — CA only so far)

- `caaspp_results` — written ELA scores (maps to each state's ELA test)
- `elpac_speaking` — oral proficiency scores (maps to each state's speaking test)
- `gap_profiles` — computed Type 4 oral-written delta per student
- `lcap_allocations` — state accountability funding aligned to interventions
- `observations` — classroom observations linked to gap profiles
- `interventions` — intervention catalog
- `intervention_assignments` — student-level intervention tracking

---

## Assessment Name Mapping

Each state uses different assessment names for the oral-written delta calculation.
These are defined in `JURISDICTIONS` in `main.py` and used by:
- The AI chat system prompt (resolves correct names per selected state)
- The frontend tab headers (shows state-correct assessment name)

Key examples:

| State | Oral Assessment | Written Assessment |
|---|---|---|
| CA | ELPAC Speaking | CAASPP ELA Claim 2 |
| TX | TELPAS Speaking | STAAR ELA |
| NY | NYSESLAT Speaking | NYSTP ELA |
| FL | BEST+ Speaking | FSA ELA |
| OH | OELPA Speaking | Ohio AIR ELA |
| OR | ELPA21 Speaking | OAKS ELA |
| All others | ACCESS Speaking (WIDA) | State-specific ELA |

---

## How the Jurisdiction Filter Works

1. User selects a state from the **Jurisdiction** dropdown
2. Frontend calls `/api/districts?state=XX`
3. Backend queries `SELECT ... FROM districts WHERE state = 'XX'`
4. District list populates with that state's LEAs only
5. User selects a district → full dashboard loads
6. AI chat receives the `state` field and resolves correct assessment names

**Default behavior:** No districts load until a state is selected (prevents
loading all 19,704 rows on page open).

---

## Running the District Migration

If the `districts` table ever needs to be rebuilt (e.g. for a new NCES year):

```bash
# Set env var first
$env:SUPABASE_SECRET_KEY = "sb_secret_..."

# Run from the repo root
python load_districts.py
```

`load_districts.py` will:
1. Fetch all LEAs from NCES EDGE MapServer (paged, ~19,700 records)
2. Clear all child tables in FK order, then clear districts
3. Insert all LEAs in batches of 500
4. Print a count-by-state verification

**NCES data source:**
`https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICLEA_2223/MapServer/0`

For a new school year, find the updated service name at:
`https://nces.ed.gov/opengis/rest/services/K12_School_Locations` (JSON catalog)

---

## Adding Assessment Data for a New State

The district list is now populated for all 51 jurisdictions but assessment
data (CAASPP, ELPAC, gap profiles, LCAP) currently only exists for California.

To add data for a new state (e.g. Texas):

1. Obtain state assessment data (STAAR ELA scores, TELPAS Speaking scores)
2. Transform to match the `caaspp_results` / `elpac_speaking` schema
3. Insert with the correct `district_id` values (matching NCES LEAID)
4. The portal will display the data automatically — no code changes needed

The `district_id` values in `caaspp_results` and `elpac_speaking` must match
the `district_id` in the `districts` table (NCES LEAID format, e.g. `4800001`).

---

## Debugging the Live Site

**Check if the service is up:**
```
https://jeremy.h-edu.solutions/health
→ {"status": "ok", "service": "VERA Research Portal"}
```

**Check if new code is deployed:**
```python
import requests
r = requests.get("https://jeremy.h-edu.solutions/")
print("new" if "Select a state above" in r.text else "old code still running")
```

**Test a state filter:**
```
https://jeremy.h-edu.solutions/api/districts?state=TX
→ {"districts": [...], "count": 1000}
```

**Browser debugging (if page hangs):**
1. Open DevTools → F12
2. **Console tab** — shows JS errors
3. **Network tab** → refresh → look for any request stuck as "pending"

**Render deploy logs:**
dashboard.render.com → vera-research-portal → **Logs** tab

---

## Environment Variables (set in Render dashboard)

| Key | Description |
|---|---|
| `SUPABASE_URL` | `https://qvzwdcqshhajtpskqmxa.supabase.co` |
| `SUPABASE_SECRET_KEY` | Service role key (from Render env panel) |
| `ANTHROPIC_API_KEY` | Claude API key for AI chat |

Never commit these to GitHub. The migration scripts read `SUPABASE_SECRET_KEY`
from the environment (`os.environ["SUPABASE_SECRET_KEY"]`).

---

## Deploying Changes

```bash
# Make changes to main.py or static/index.html
git add .
git commit -m "description of change"
git push
# Render auto-deploys in ~2 minutes
```

GitHub secret scanning is enabled on the repo — never hardcode API keys
or Supabase credentials in any committed file.
