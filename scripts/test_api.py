"""
Phase 4 integration test: exercises the REST API end-to-end.

Prerequisites:
  1. Server running:  uvicorn app.main:app --reload  (from delphee-lead-hunter/)
  2. pip install httpx websockets

Usage:
  python scripts/test_api.py [--base-url http://localhost:8000]

  Use --small-region to scan "Eastern Europe" (4 countries) instead of "Sub-Saharan Africa"
  for a quicker end-to-end smoke test.
"""
import argparse
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import httpx
    import websockets
except ImportError:
    print("Missing deps -- run: pip install httpx websockets")
    sys.exit(1)


BASE_URL = "http://localhost:8000"
# 30 s for quick reads; POST /scans may wait briefly for a DB write lock
REQUEST_TIMEOUT = 60


def ok(label: str):
    print(f"  [PASS] {label}")


def fail(label: str, detail: str = ""):
    print(f"  [FAIL] {label}" + (f": {detail}" if detail else ""))
    sys.exit(1)


# ── Health check ──────────────────────────────────────────────────────────────

async def test_health(client: httpx.AsyncClient):
    print("\n=== Health Check ===")
    r = await client.get("/health")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    ok("GET /health")


# ── Regions ───────────────────────────────────────────────────────────────────

async def test_regions(client: httpx.AsyncClient):
    print("\n=== Regions ===")
    r = await client.get("/api/regions")
    assert r.status_code == 200, r.text
    regions = r.json()
    assert isinstance(regions, dict)
    assert "Sub-Saharan Africa" in regions
    ok(f"GET /api/regions -- {len(regions)} regions returned")


# ── Start scan ────────────────────────────────────────────────────────────────

async def test_start_scan(client: httpx.AsyncClient, region: str) -> str:
    print(f"\n=== Start Scan ({region}) ===")
    r = await client.post("/api/scans", json={"regions": [region]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "scan_id" in body
    assert body["status"] == "started"
    scan_id = body["scan_id"]
    ok(f"POST /api/scans -> scan_id={scan_id}")
    return scan_id


# ── WebSocket progress ────────────────────────────────────────────────────────

async def watch_websocket(scan_id: str, base_url: str):
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws/scans/{scan_id}"
    print(f"\n=== WebSocket: {ws_url} ===")

    phases_seen = set()
    # open_timeout=None: works around a Python 3.14 asyncio.timeout compatibility issue
    async with websockets.connect(ws_url, open_timeout=None) as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=360)
                msg = json.loads(raw)
                phase = msg.get("phase", "?")
                phases_seen.add(phase)

                if phase == "ping":
                    print("  [WS] keep-alive ping")
                elif phase == "complete":
                    print(f"  [WS] complete -- total={msg.get('total_found')} active={msg.get('active_count')}")
                    ok("WebSocket received 'complete'")
                    break
                elif phase == "error":
                    fail("WebSocket received 'error'", msg.get("message", ""))
                else:
                    print(f"  [WS] {phase}: {msg.get('message', '')} ({msg.get('current')}/{msg.get('total')})")

            except asyncio.TimeoutError:
                fail("WebSocket timed out waiting for completion (>6 min)")

    return phases_seen


# ── Poll until complete ───────────────────────────────────────────────────────

async def poll_until_complete(client: httpx.AsyncClient, scan_id: str, timeout: int = 420) -> dict:
    print(f"\n=== Polling scan {scan_id} ===")
    elapsed = 0
    while elapsed < timeout:
        r = await client.get(f"/api/scans/{scan_id}")
        assert r.status_code == 200, r.text
        scan = r.json()
        status = scan["status"]
        print(f"  status={status}  total_found={scan.get('total_found', 0)}")
        if status == "completed":
            ok(f"Scan completed -- total_found={scan['total_found']} active={scan['active_count']}")
            return scan
        if status == "failed":
            fail("Scan status is 'failed'")
        await asyncio.sleep(10)
        elapsed += 10

    fail(f"Scan did not complete within {timeout}s")


# ── Validate stored leads ─────────────────────────────────────────────────────

async def test_leads(client: httpx.AsyncClient, scan_id: str):
    print("\n=== Leads API ===")

    # Scan detail (embedded leads)
    r = await client.get(f"/api/scans/{scan_id}")
    assert r.status_code == 200, r.text
    scan_detail = r.json()
    leads_in_scan = scan_detail.get("leads", [])
    ok(f"GET /api/scans/{scan_id} -- {len(leads_in_scan)} leads embedded")

    # Global leads list
    r = await client.get("/api/leads?limit=100")
    assert r.status_code == 200, r.text
    all_leads = r.json()
    ok(f"GET /api/leads -- {len(all_leads)} leads")

    # Filter by min_score
    r = await client.get("/api/leads?min_score=50")
    assert r.status_code == 200
    high = r.json()
    ok(f"GET /api/leads?min_score=50 -- {len(high)} leads")

    # Filter by freshness=active
    r = await client.get("/api/leads?freshness=active")
    assert r.status_code == 200
    active = r.json()
    ok(f"GET /api/leads?freshness=active -- {len(active)} leads")

    # Filter by freshness=actionable (active + stale)
    r = await client.get("/api/leads?freshness=actionable")
    assert r.status_code == 200
    actionable = r.json()
    ok(f"GET /api/leads?freshness=actionable -- {len(actionable)} leads")

    # Sort by first_seen_at
    r = await client.get("/api/leads?sort_by=first_seen_at&limit=10")
    assert r.status_code == 200
    ok("GET /api/leads?sort_by=first_seen_at")

    if all_leads:
        lead_id = all_leads[0]["id"]

        # PATCH a lead
        r = await client.patch(f"/api/leads/{lead_id}", json={
            "lead_status": "contacted",
            "notes": "API test note",
        })
        assert r.status_code == 200, r.text
        patched = r.json()
        assert patched["lead_status"] == "contacted"
        assert patched["notes"] == "API test note"
        ok(f"PATCH /api/leads/{lead_id}")

    # Top 5 summary
    top5 = sorted(all_leads, key=lambda l: l.get("relevance_score") or 0, reverse=True)[:5]
    print("\n  Top 5 by relevance:")
    for l in top5:
        score = l.get("relevance_score", 0) or 0
        freshness = (l.get("freshness") or "?")[:8]
        urgency = (l.get("urgency") or "?")[:6]
        title = (l.get("title") or "")[:65]
        print(f"    [{score:>3}] [{freshness:>8}] [{urgency:>6}] {title}")


# ── CSV export ────────────────────────────────────────────────────────────────

async def test_export(client: httpx.AsyncClient):
    print("\n=== CSV Export ===")
    r = await client.get("/api/leads/export")
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    lines = r.text.strip().splitlines()
    ok(f"GET /api/leads/export -- {len(lines)} lines (including header)")

    r = await client.get("/api/leads/export?freshness=active&min_score=40")
    assert r.status_code == 200
    ok("GET /api/leads/export?freshness=active&min_score=40")


# ── List scans ────────────────────────────────────────────────────────────────

async def test_list_scans(client: httpx.AsyncClient):
    print("\n=== List Scans ===")
    r = await client.get("/api/scans")
    assert r.status_code == 200, r.text
    scans = r.json()
    assert isinstance(scans, list)
    assert len(scans) > 0
    ok(f"GET /api/scans -- {len(scans)} scan(s)")


# ── Main ──────────────────────────────────────────────────────────────────────

async def run_all(base_url: str, skip_websocket: bool, region: str):
    async with httpx.AsyncClient(base_url=base_url, timeout=REQUEST_TIMEOUT) as client:
        await test_health(client)
        await test_regions(client)
        scan_id = await test_start_scan(client, region)

        if not skip_websocket:
            phases = await watch_websocket(scan_id, base_url)
            print(f"  WebSocket phases seen: {sorted(phases)}")
        else:
            await poll_until_complete(client, scan_id)

        await test_leads(client, scan_id)
        await test_export(client)
        await test_list_scans(client)

    print("\n=== All checks passed ===\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--no-websocket", action="store_true",
                        help="Skip WebSocket test, poll REST instead")
    parser.add_argument("--small-region", action="store_true",
                        help="Use Eastern Europe (4 countries) for a faster smoke test")
    args = parser.parse_args()
    region = "Eastern Europe" if args.small_region else "Sub-Saharan Africa"
    asyncio.run(run_all(args.base_url, args.no_websocket, region))
