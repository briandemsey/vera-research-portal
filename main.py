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


# ── Districts ─────────────────────────────────────────────────────────────────

@app.get("/api/districts")
async def get_districts():
    """Return all districts in the VERA database."""
    try:
        result = supabase.table("districts") \
            .select("district_id, district_name, county") \
            .order("district_name") \
            .execute()
        return {"districts": result.data, "count": len(result.data)}
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

        system_prompt = f"""You are VERA Research Assistant, the AI research interface for H-EDU.Solutions' 
Verification Engine for Results & Accountability (VERA).

You help education researchers, CSBA staff, and county office of education reviewers 
understand and interpret VERA data. You are speaking with Jeremy Anderson, 
Principal Research Manager at CSBA's Closing the Achievement Gap initiative.

VERA computes the oral-written delta: the gap between a student's ELPAC Speaking 
(oral proficiency) score and their CAASPP ELA Claim 2 (written expression) score. 
Students with a delta of 8 or more points are flagged as Type 4 candidates — 
students whose oral language strength is significantly exceeding their written 
expression, indicating an unmet instructional need that LCAP funding should address.

Key terminology:
- Oral-written delta: ELPAC Speaking score minus CAASPP ELA Claim 2 score
- Type 4 gap: delta >= 8 points, indicating oral strength masked by weak written scores
- LCAP match rate: percentage of LCAP-funded interventions that align to verified Type 4 gaps
- Gap match verified: a human reviewer has confirmed the gap profile is accurate
- COE reviewed: a County Office of Education reviewer has signed off on the LCAP allocation

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
