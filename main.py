"""
VERA Research Portal — Backend API
H-EDU.Solutions | jeremy.h-edu.solutions
FastAPI + Supabase + Anthropic Claude
"""

import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from supabase import create_client, Client
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Clients ───────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qvzwdcqshhajtpskqmxa.supabase.co")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Jurisdiction metadata ─────────────────────────────────────────────────────

# Maps state abbreviation → display name and primary assessment labels.
# oral_assessment: the speaking/oral proficiency assessment used in that state.
# written_assessment: the ELA written assessment used to compute the delta.
JURISDICTIONS: dict[str, dict] = {
    "AL": {"name": "Alabama",        "oral_assessment": "ACCESS Speaking", "written_assessment": "ACAP ELA"},
    "AK": {"name": "Alaska",         "oral_assessment": "WIDA ACCESS Speaking", "written_assessment": "AMP ELA"},
    "AZ": {"name": "Arizona",        "oral_assessment": "AZELLA Speaking", "written_assessment": "AzM2 ELA"},
    "AR": {"name": "Arkansas",       "oral_assessment": "ACCESS Speaking", "written_assessment": "ATLAS ELA"},
    "CA": {"name": "California",     "oral_assessment": "ELPAC Speaking", "written_assessment": "CAASPP ELA Claim 2"},
    "CO": {"name": "Colorado",       "oral_assessment": "CELA Speaking", "written_assessment": "CMAS ELA"},
    "CT": {"name": "Connecticut",    "oral_assessment": "ACCESS Speaking", "written_assessment": "SBAC ELA"},
    "DE": {"name": "Delaware",       "oral_assessment": "ACCESS Speaking", "written_assessment": "SBAC ELA"},
    "DC": {"name": "District of Columbia", "oral_assessment": "ACCESS Speaking", "written_assessment": "PARCC ELA"},
    "FL": {"name": "Florida",        "oral_assessment": "BEST+ Speaking", "written_assessment": "FSA ELA"},
    "GA": {"name": "Georgia",        "oral_assessment": "ACCESS Speaking", "written_assessment": "Georgia Milestones ELA"},
    "HI": {"name": "Hawaii",         "oral_assessment": "ACCESS Speaking", "written_assessment": "SBAC ELA"},
    "ID": {"name": "Idaho",          "oral_assessment": "ACCESS Speaking", "written_assessment": "ISAT ELA"},
    "IL": {"name": "Illinois",       "oral_assessment": "ACCESS Speaking", "written_assessment": "IAR ELA"},
    "IN": {"name": "Indiana",        "oral_assessment": "ACCESS Speaking", "written_assessment": "ILEARN ELA"},
    "IA": {"name": "Iowa",           "oral_assessment": "ACCESS Speaking", "written_assessment": "Iowa Statewide Assessment"},
    "KS": {"name": "Kansas",         "oral_assessment": "ACCESS Speaking", "written_assessment": "Kansas Assessment ELA"},
    "KY": {"name": "Kentucky",       "oral_assessment": "ACCESS Speaking", "written_assessment": "KSA ELA"},
    "LA": {"name": "Louisiana",      "oral_assessment": "ACCESS Speaking", "written_assessment": "LEAP 2025 ELA"},
    "ME": {"name": "Maine",          "oral_assessment": "ACCESS Speaking", "written_assessment": "MEA ELA"},
    "MD": {"name": "Maryland",       "oral_assessment": "ACCESS Speaking", "written_assessment": "MCAP ELA"},
    "MA": {"name": "Massachusetts",  "oral_assessment": "ACCESS Speaking", "written_assessment": "MCAS ELA"},
    "MI": {"name": "Michigan",       "oral_assessment": "ACCESS Speaking", "written_assessment": "M-STEP ELA"},
    "MN": {"name": "Minnesota",      "oral_assessment": "ACCESS Speaking", "written_assessment": "MCA ELA"},
    "MS": {"name": "Mississippi",    "oral_assessment": "ACCESS Speaking", "written_assessment": "MAAP ELA"},
    "MO": {"name": "Missouri",       "oral_assessment": "ACCESS Speaking", "written_assessment": "MAP ELA"},
    "MT": {"name": "Montana",        "oral_assessment": "ACCESS Speaking", "written_assessment": "MontCAS ELA"},
    "NE": {"name": "Nebraska",       "oral_assessment": "ACCESS Speaking", "written_assessment": "NSCAS ELA"},
    "NV": {"name": "Nevada",         "oral_assessment": "ACCESS Speaking", "written_assessment": "SBAC ELA"},
    "NH": {"name": "New Hampshire",  "oral_assessment": "ACCESS Speaking", "written_assessment": "NHSAS ELA"},
    "NJ": {"name": "New Jersey",     "oral_assessment": "ACCESS Speaking", "written_assessment": "NJSLA ELA"},
    "NM": {"name": "New Mexico",     "oral_assessment": "ACCESS Speaking", "written_assessment": "NMAM ELA"},
    "NY": {"name": "New York",       "oral_assessment": "NYSESLAT Speaking", "written_assessment": "NYSTP ELA"},
    "NC": {"name": "North Carolina", "oral_assessment": "ACCESS Speaking", "written_assessment": "NC Check-Ins ELA"},
    "ND": {"name": "North Dakota",   "oral_assessment": "ACCESS Speaking", "written_assessment": "NDSA ELA"},
    "OH": {"name": "Ohio",           "oral_assessment": "OELPA Speaking", "written_assessment": "Ohio AIR ELA"},
    "OK": {"name": "Oklahoma",       "oral_assessment": "ACCESS Speaking", "written_assessment": "OSTP ELA"},
    "OR": {"name": "Oregon",         "oral_assessment": "ELPA21 Speaking", "written_assessment": "OAKS ELA"},
    "PA": {"name": "Pennsylvania",   "oral_assessment": "ACCESS Speaking", "written_assessment": "PSSA ELA"},
    "RI": {"name": "Rhode Island",   "oral_assessment": "ACCESS Speaking", "written_assessment": "RICAS ELA"},
    "SC": {"name": "South Carolina", "oral_assessment": "ACCESS Speaking", "written_assessment": "SC READY ELA"},
    "SD": {"name": "South Dakota",   "oral_assessment": "ACCESS Speaking", "written_assessment": "SDSA ELA"},
    "TN": {"name": "Tennessee",      "oral_assessment": "ACCESS Speaking", "written_assessment": "TNReady ELA"},
    "TX": {"name": "Texas",          "oral_assessment": "TELPAS Speaking", "written_assessment": "STAAR ELA"},
    "UT": {"name": "Utah",           "oral_assessment": "UTAH ELPA Speaking", "written_assessment": "RISE ELA"},
    "VT": {"name": "Vermont",        "oral_assessment": "ACCESS Speaking", "written_assessment": "SBAC ELA"},
    "VA": {"name": "Virginia",       "oral_assessment": "ACCESS Speaking", "written_assessment": "SOL ELA"},
    "WA": {"name": "Washington",     "oral_assessment": "ELPA21 Speaking", "written_assessment": "SBAC ELA"},
    "WV": {"name": "West Virginia",  "oral_assessment": "ACCESS Speaking", "written_assessment": "WV General Summative"},
    "WI": {"name": "Wisconsin",      "oral_assessment": "ACCESS Speaking", "written_assessment": "Forward ELA"},
    "WY": {"name": "Wyoming",        "oral_assessment": "ACCESS Speaking", "written_assessment": "WY-TOPP ELA"},
}

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VERA Research Portal",
    description="H-EDU Verification Engine for Results & Accountability — Research API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (frontend) ───────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("static/index.html")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "VERA Research Portal"}


# ── Jurisdictions ─────────────────────────────────────────────────────────────

@app.get("/api/jurisdictions")
async def get_jurisdictions():
    """Return the full list of US state jurisdictions VERA supports."""
    return {
        "jurisdictions": [
            {"state": abbr, **meta}
            for abbr, meta in sorted(JURISDICTIONS.items(), key=lambda x: x[1]["name"])
        ],
        "count": len(JURISDICTIONS),
    }


# ── Districts ─────────────────────────────────────────────────────────────────

@app.get("/api/districts")
async def get_districts(state: Optional[str] = None):
    """Return districts, optionally filtered by state abbreviation."""
    try:
        # Supabase caps a single response at 1000 rows, so page through
        # with .range() until we get a short page. CA has ~2,147 LEAs.
        PAGE = 1000
        rows: list = []
        start = 0
        while True:
            query = supabase.table("districts") \
                .select("district_id, district_name, county, state") \
                .order("district_name") \
                .range(start, start + PAGE - 1)
            if state:
                query = query.eq("state", state.upper())
            page = query.execute().data or []
            rows.extend(page)
            if len(page) < PAGE:
                break
            start += PAGE
        return {"districts": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/districts/{district_id}")
async def get_district(district_id: str):
    """Return a single district record."""
    try:
        result = supabase.table("districts") \
            .select("*") \
            .eq("district_id", district_id) \
            .single() \
            .execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="District not found")
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── CAASPP Results ────────────────────────────────────────────────────────────

@app.get("/api/districts/{district_id}/caaspp")
async def get_caaspp(
    district_id: str,
    year: Optional[int] = None,
    grade: Optional[int] = None,
):
    """Return CAASPP ELA results for a district, optionally filtered by year/grade."""
    try:
        query = supabase.table("caaspp_results") \
            .select("*") \
            .eq("district_id", district_id) \
            .order("year", desc=True) \
            .order("grade")
        if year:
            query = query.eq("year", year)
        if grade:
            query = query.eq("grade", grade)
        result = query.execute()
        return {"district_id": district_id, "caaspp": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ELPAC Speaking ────────────────────────────────────────────────────────────

@app.get("/api/districts/{district_id}/elpac")
async def get_elpac(
    district_id: str,
    year: Optional[int] = None,
    grade: Optional[int] = None,
):
    """Return ELPAC Speaking results for a district."""
    try:
        query = supabase.table("elpac_speaking") \
            .select("*") \
            .eq("district_id", district_id) \
            .order("year", desc=True) \
            .order("grade")
        if year:
            query = query.eq("year", year)
        if grade:
            query = query.eq("grade", grade)
        result = query.execute()
        return {"district_id": district_id, "elpac": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Gap Profiles (Type 4 Flags) ───────────────────────────────────────────────

@app.get("/api/districts/{district_id}/gaps")
async def get_gap_profiles(
    district_id: str,
    verified_only: bool = False,
    min_delta: Optional[float] = None,
):
    """Return oral-written delta gap profiles for a district."""
    try:
        query = supabase.table("gap_profiles") \
            .select("*") \
            .eq("district_id", district_id) \
            .order("oral_written_delta", desc=True)
        if verified_only:
            query = query.eq("gap_match_verified", True)
        if min_delta is not None:
            query = query.gte("oral_written_delta", min_delta)
        result = query.execute()
        return {"district_id": district_id, "gap_profiles": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gaps/all")
async def get_all_gaps(
    min_delta: Optional[float] = Query(None, description="Minimum oral-written delta"),
    verified_only: bool = False,
    limit: int = Query(500, le=2000),
):
    """Return gap profiles across all districts — for cross-district research queries."""
    try:
        query = supabase.table("gap_profiles") \
            .select("*, districts(district_name, county)") \
            .order("oral_written_delta", desc=True) \
            .limit(limit)
        if verified_only:
            query = query.eq("gap_match_verified", True)
        if min_delta is not None:
            query = query.gte("oral_written_delta", min_delta)
        result = query.execute()
        return {"gap_profiles": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LCAP Allocations ──────────────────────────────────────────────────────────

@app.get("/api/districts/{district_id}/lcap")
async def get_lcap(district_id: str):
    """Return LCAP allocations and match rates for a district."""
    try:
        result = supabase.table("lcap_allocations") \
            .select("*, interventions(name, description, evidence_tier)") \
            .eq("district_id", district_id) \
            .order("fiscal_year", desc=True) \
            .execute()
        return {"district_id": district_id, "lcap": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Observations ──────────────────────────────────────────────────────────────

@app.get("/api/districts/{district_id}/observations")
async def get_observations(
    district_id: str,
    limit: int = Query(200, le=1000),
):
    """Return classroom observations linked to gap profiles for a district."""
    try:
        # observations link through gap_profiles, so join via gap_profiles
        gaps = supabase.table("gap_profiles") \
            .select("id") \
            .eq("district_id", district_id) \
            .execute()
        gap_ids = [g["id"] for g in gaps.data]
        if not gap_ids:
            return {"district_id": district_id, "observations": [], "count": 0}
        result = supabase.table("observations") \
            .select("*") \
            .in_("gap_profile_id", gap_ids) \
            .order("observation_date", desc=True) \
            .limit(limit) \
            .execute()
        return {"district_id": district_id, "observations": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Interventions ─────────────────────────────────────────────────────────────

@app.get("/api/interventions")
async def get_interventions():
    """Return the full intervention catalog."""
    try:
        result = supabase.table("interventions") \
            .select("*") \
            .order("evidence_tier") \
            .execute()
        return {"interventions": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/districts/{district_id}/intervention-assignments")
async def get_intervention_assignments(district_id: str):
    """Return intervention assignments for students in a district."""
    try:
        gaps = supabase.table("gap_profiles") \
            .select("id") \
            .eq("district_id", district_id) \
            .execute()
        gap_ids = [g["id"] for g in gaps.data]
        if not gap_ids:
            return {"district_id": district_id, "assignments": [], "count": 0}
        result = supabase.table("intervention_assignments") \
            .select("*, interventions(name, evidence_tier)") \
            .in_("gap_profile_id", gap_ids) \
            .order("assigned_date", desc=True) \
            .execute()
        return {"district_id": district_id, "assignments": result.data, "count": len(result.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Summary (dashboard overview card) ─────────────────────────────────────────

@app.get("/api/districts/{district_id}/summary")
async def get_district_summary(district_id: str):
    """Return a high-level summary card for a district — used by the dashboard header."""
    try:
        # District info
        district = supabase.table("districts") \
            .select("*") \
            .eq("district_id", district_id) \
            .single() \
            .execute()

        # Gap profile stats
        gaps = supabase.table("gap_profiles") \
            .select("oral_written_delta, gap_match_verified, confidence_score") \
            .eq("district_id", district_id) \
            .execute()

        # LCAP summary
        lcap = supabase.table("lcap_allocations") \
            .select("match_rate, coe_reviewed, allocation_amount") \
            .eq("district_id", district_id) \
            .execute()

        gap_data = gaps.data or []
        lcap_data = lcap.data or []

        total_gaps = len(gap_data)
        verified_gaps = sum(1 for g in gap_data if g.get("gap_match_verified"))
        avg_delta = round(
            sum(g["oral_written_delta"] for g in gap_data if g.get("oral_written_delta")) / total_gaps, 2
        ) if total_gaps else 0
        max_delta = round(
            max((g["oral_written_delta"] for g in gap_data if g.get("oral_written_delta")), default=0), 2
        )
        avg_lcap_match = round(
            sum(l["match_rate"] for l in lcap_data if l.get("match_rate")) / len(lcap_data), 2
        ) if lcap_data else 0
        total_allocation = sum(float(l["allocation_amount"] or 0) for l in lcap_data)
        coe_reviewed = any(l.get("coe_reviewed") for l in lcap_data)

        return {
            "district": district.data,
            "summary": {
                "total_gap_profiles": total_gaps,
                "verified_gap_profiles": verified_gaps,
                "average_oral_written_delta": avg_delta,
                "max_oral_written_delta": max_delta,
                "average_lcap_match_rate": avg_lcap_match,
                "total_lcap_allocation": total_allocation,
                "coe_reviewed": coe_reviewed,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    state: Optional[str] = None
    context_summary: Optional[str] = None  # JSON string of current dashboard data


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    AI chat endpoint. Claude receives the researcher's question plus
    the current district context so it can answer with real VERA data.
    """
    try:
        # Build context from whatever district data the frontend passes in
        context_block = ""
        if req.context_summary:
            try:
                ctx = json.loads(req.context_summary)
                context_block = f"""
Current dashboard context (live VERA data):
District: {ctx.get('district_name', req.district_name or 'Not selected')}
Total gap profiles: {ctx.get('total_gap_profiles', 'N/A')}
Verified gaps: {ctx.get('verified_gap_profiles', 'N/A')}
Average oral-written delta: {ctx.get('average_oral_written_delta', 'N/A')}
Maximum oral-written delta: {ctx.get('max_oral_written_delta', 'N/A')}
Average LCAP match rate: {ctx.get('average_lcap_match_rate', 'N/A')}
Total LCAP allocation: ${ctx.get('total_lcap_allocation', 0):,.2f}
COE reviewed: {ctx.get('coe_reviewed', 'N/A')}
"""
            except Exception:
                context_block = f"District: {req.district_name or 'Not selected'}"

        # Resolve jurisdiction-specific assessment names for the current district
        state_code = req.state or (req.context_summary and json.loads(req.context_summary or "{}").get("state")) or ""
        jx = JURISDICTIONS.get(state_code.upper(), {})
        oral_label = jx.get("oral_assessment", "oral proficiency assessment")
        written_label = jx.get("written_assessment", "ELA written assessment")
        state_name = jx.get("name", "this state") if state_code else "this jurisdiction"

        system_prompt = f"""You are VERA Research Assistant, the AI research interface for H-EDU.Solutions'
Verification Engine for Results & Accountability (VERA).

You help education researchers, state education agency staff, and accountability
reviewers understand and interpret VERA data across all 50 US states and DC.

VERA computes the oral-written delta: the gap between a student's oral proficiency
assessment score and their written ELA assessment score. Students with a delta of
8 or more points are flagged as Type 4 candidates — students whose oral language
strength significantly exceeds their written expression, indicating an unmet
instructional need that state accountability funding should address.

{f"For the currently selected district in {state_name}:" if state_code else "General VERA context:"}
- Oral proficiency assessment: {oral_label}
- Written ELA assessment: {written_label}
- Oral-written delta = {oral_label} score minus {written_label} score
- Type 4 gap: delta >= 8 points
- Funding match rate: % of state accountability funding interventions aligned to verified Type 4 gaps
- Gap match verified: a human reviewer has confirmed the gap profile is accurate
- Accountability office reviewed: a state/county accountability office has signed off on funding alignment

{context_block}

Answer questions clearly and precisely. When referencing data, be specific about
what the numbers mean for students and policy. If asked something outside VERA's
scope, say so clearly. Keep responses concise — three to five sentences unless
the question requires more depth. Never invent data not provided in the context."""

        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": req.message}]
        )

        return {
            "response": response.content[0].text,
            "model": response.model,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
