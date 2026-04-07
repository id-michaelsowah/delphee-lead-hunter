import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.db_factory import get_repository
from app.models import (
    LeadResponse,
    ScanRunDetailResponse,
    ScanRunResponse,
    StartScanRequest,
    UpdateLeadRequest,
)
from app.scanner.regions import REGIONS, get_regions
from app.api.websocket import send_progress, send_complete, send_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Scans ─────────────────────────────────────────────────────────────────────

@router.post("/scans", response_model=dict, tags=["scans"])
async def start_scan(body: StartScanRequest, background_tasks: BackgroundTasks):
    """Trigger a new scan for one or more regions."""
    scan_id = str(uuid.uuid4())
    repo = get_repository()
    await repo.create_scan_run({
        "id": scan_id,
        "regions": body.regions,
        "status": "running",
        "triggered_by": "api",
    })
    background_tasks.add_task(run_scan_pipeline, scan_id, body.regions)
    return {"scan_id": scan_id, "status": "started"}


@router.get("/scans", response_model=list[ScanRunResponse], tags=["scans"])
async def list_scans(limit: int = Query(20, ge=1, le=100)):
    """List recent scan runs."""
    repo = get_repository()
    scans = await repo.list_scan_runs(limit=limit)
    return scans


@router.get("/scans/{scan_id}", response_model=ScanRunDetailResponse, tags=["scans"])
async def get_scan(scan_id: str):
    """Get a specific scan including all its leads."""
    repo = get_repository()
    scan = await repo.get_scan_run(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    leads = await repo.list_leads(
        filters={"scan_run_id": scan_id},
        sort_by="relevance_score",
        limit=1000,
        offset=0,
    )
    scan["leads"] = leads
    return scan


# ── Leads ─────────────────────────────────────────────────────────────────────

@router.get("/leads", response_model=list[LeadResponse], tags=["leads"])
async def list_leads(
    freshness: Optional[str] = None,
    type: Optional[str] = None,
    country: Optional[str] = None,
    min_score: int = Query(0, ge=0, le=100),
    sort_by: str = Query("relevance_score", pattern="^(relevance_score|urgency|freshness|first_seen_at)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Browse and filter leads across all scans."""
    repo = get_repository()
    filters = {
        "freshness": freshness,
        "type": type,
        "country": country,
        "min_score": min_score,
    }
    filters = {k: v for k, v in filters.items() if v is not None and v != 0 or k == "min_score"}
    return await repo.list_leads(filters=filters, sort_by=sort_by, limit=limit, offset=offset)


@router.patch("/leads/{lead_id}", response_model=LeadResponse, tags=["leads"])
async def update_lead(lead_id: str, body: UpdateLeadRequest):
    """Update a lead's tracking fields."""
    repo = get_repository()
    lead = await repo.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return lead
    return await repo.update_lead(lead_id, updates)


@router.get("/leads/export", tags=["leads"])
async def export_leads(
    freshness: Optional[str] = None,
    type: Optional[str] = None,
    country: Optional[str] = None,
    min_score: int = Query(0, ge=0, le=100),
):
    """Export filtered leads as a CSV download."""
    repo = get_repository()
    filters = {k: v for k, v in {
        "freshness": freshness,
        "type": type,
        "country": country,
        "min_score": min_score,
    }.items() if v is not None}

    leads = await repo.list_leads(
        filters=filters,
        sort_by="relevance_score",
        limit=10000,
        offset=0,
    )

    output = io.StringIO()
    fieldnames = [
        "title", "institution", "country", "type", "freshness", "urgency",
        "relevance_score", "deadline", "published_date", "summary",
        "relevance_reason", "follow_up_action", "contact_info",
        "source_url", "lead_status", "assigned_to", "notes", "first_seen_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(leads)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=delphee-leads.csv"},
    )


# ── Scan actions ─────────────────────────────────────────────────────────────

@router.post("/scans/{scan_id}/cancel", response_model=ScanRunResponse, tags=["scans"])
async def cancel_scan(scan_id: str):
    """Mark a stuck running scan as failed."""
    repo = get_repository()
    scan = await repo.get_scan_run(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan["status"] != "running":
        raise HTTPException(status_code=400, detail=f"Scan is '{scan['status']}' — only running scans can be cancelled")
    return await repo.update_scan_run(scan_id, {
        "status": "failed",
        "completed_at": datetime.utcnow(),
    })


# ── Regions ───────────────────────────────────────────────────────────────────

@router.get("/regions", tags=["config"])
async def list_regions():
    """Return available regions and their countries."""
    return get_regions()


# ── Usage & cost tracking ─────────────────────────────────────────────────────

@router.get("/usage", tags=["config"])
async def get_usage(month: Optional[str] = None):
    """Return token usage and estimated API costs for the given month (default: current)."""
    from app.usage_tracker import get_summary
    return get_summary(month)


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_scan_pipeline(scan_id: str, regions: list[str]):
    """Full pipeline: discover → analyze → dedup → store."""
    from app.scanner.discovery import discover_opportunities
    from app.scanner.analysis import analyze_opportunities
    from app.scanner.dedup import deduplicate

    repo = get_repository()

    try:
        # Collect countries from selected regions
        countries: list[str] = []
        for region in regions:
            countries.extend(REGIONS.get(region, []))

        if not countries:
            await repo.update_scan_run(scan_id, {"status": "failed"})
            return

        # ── Phase 1: Discovery (Gemini) ────────────────────────────────────
        async def discovery_progress(msg: str, current: int, total: int):
            await send_progress(scan_id, "discovery", msg, current, total)

        raw = await discover_opportunities(countries, on_progress=discovery_progress)
        logger.info("Scan %s: %d raw results discovered", scan_id, len(raw))

        # ── Phase 2: Analysis (Claude) ─────────────────────────────────────
        async def analysis_progress(msg: str, current: int, total: int):
            await send_progress(scan_id, "analysis", msg, current, total)

        scored = await analyze_opportunities(raw, on_progress=analysis_progress)
        logger.info("Scan %s: %d results after scoring", scan_id, len(scored))

        # ── Phase 3: Deduplication ─────────────────────────────────────────
        existing_titles = await repo.get_existing_lead_titles()
        final = deduplicate(scored, existing_titles)
        logger.info("Scan %s: %d unique leads after dedup", scan_id, len(final))

        # ── Phase 4: Persist ───────────────────────────────────────────────
        for lead in final:
            lead["scan_run_id"] = scan_id

        if final:
            await repo.create_leads_batch(final)

        active_count = sum(1 for l in final if l.get("freshness") in ("active", "stale"))
        await repo.update_scan_run(scan_id, {
            "status": "completed",
            "total_found": len(final),
            "active_count": active_count,
            "completed_at": datetime.utcnow(),
        })

        await send_complete(scan_id, len(final), active_count)
        logger.info("Scan %s completed: %d leads, %d active", scan_id, len(final), active_count)

    except Exception as exc:
        logger.exception("Scan %s failed: %s", scan_id, exc)
        await repo.update_scan_run(scan_id, {"status": "failed"})
        await send_error(scan_id, str(exc))
