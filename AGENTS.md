# VERA Research Portal — AGENTS.md

## Purpose
This is the VERA Research Portal, a public-facing research interface for H-EDU.Solutions'
Verification Engine for Results & Accountability (VERA). It is deployed at jeremy.h-edu.solutions
and serves researchers, CSBA staff, and County Office of Education reviewers.

## Architecture
- **Backend:** FastAPI (Python), deployed on Render.com
- **Frontend:** Single-file HTML/CSS/JS in static/index.html, served by FastAPI
- **Database:** Supabase PostgreSQL (project: qvzwdcqshhajtpskqmxa)
- **AI Chat:** Anthropic Claude API (claude-sonnet-4-6)

## File Structure
```
vera-research-portal/
├── main.py              # FastAPI backend — all API endpoints + AI chat
├── requirements.txt     # Python dependencies
├── render.yaml          # Render.com deployment configuration
├── .gitignore           # Excludes .env from GitHub
├── AGENTS.md            # This file
├── DEPLOY.md            # Step-by-step deployment instructions
└── static/
    └── index.html       # Complete frontend — dashboard + AI chat panel
```

## Database Tables (Supabase public schema)
- `districts` — master district list (district_id, district_name, county, **state** — 2-char US abbreviation)
- `caaspp_results` — written ELA assessment scores (claim1-4, pct_met_exceeded, by grade/subgroup/year; maps to each state's ELA assessment)
- `elpac_speaking` — oral proficiency assessment scores (pct_level3_4, by grade/subgroup/year; maps to each state's speaking assessment)
- `gap_profiles` — computed Type 4 gap per student (oral_written_delta, gap_type, confidence_score)
- `observations` — daily classroom observations (linked via gap_profile_id)
- `lcap_allocations` — state accountability funding matched to interventions (match_rate, allocation_amount; named LCAP in CA, generic elsewhere)
- `interventions` — intervention catalog (name, evidence_tier, target_gap_types)
- `intervention_assignments` — student-level intervention tracking (status, outcome_notes)
- `audit_log` — system audit trail (never exposed via API)

**Required Supabase migration:** Add `state TEXT` column to the `districts` table and populate it with the 2-char US state abbreviation for every district row. This enables the `/api/districts?state=TX` filter.

## Key Domain Concepts
- **Oral-written delta:** ELPAC Speaking score minus CAASPP ELA Claim 2 score
- **Type 4 gap:** oral_written_delta >= 8 points — student's oral strength exceeds written scores
- **LCAP match rate:** % of LCAP-funded interventions aligned to verified Type 4 gaps
- **COE reviewed:** County Office of Education has signed off on LCAP allocation

## API Endpoints
All endpoints are read-only. No writes are permitted from this portal.

- GET /health
- GET /api/jurisdictions — returns all 51 supported US jurisdictions with assessment label metadata
- GET /api/districts?state=XX — returns districts, optionally filtered by 2-char state abbreviation
- GET /api/districts/{district_id}
- GET /api/districts/{district_id}/summary
- GET /api/districts/{district_id}/caaspp
- GET /api/districts/{district_id}/elpac
- GET /api/districts/{district_id}/gaps
- GET /api/gaps/all
- GET /api/districts/{district_id}/lcap
- GET /api/districts/{district_id}/observations
- GET /api/districts/{district_id}/intervention-assignments
- GET /api/interventions
- POST /api/chat

## Environment Variables (set in Render dashboard — never in code)
- SUPABASE_URL
- SUPABASE_SECRET_KEY
- ANTHROPIC_API_KEY

## Do Not
- Add write endpoints — this is a read-only research portal
- Expose the audit_log table via API
- Commit .env to GitHub
- Change the AI chat model without updating this file
- Add authentication — this portal is intentionally public for research access
