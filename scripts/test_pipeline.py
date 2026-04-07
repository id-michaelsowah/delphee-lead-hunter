"""
End-to-end pipeline test: discovery → analysis → dedup.
Usage: python scripts/test_pipeline.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.scanner.discovery import discover_opportunities
from app.scanner.analysis import analyze_opportunities
from app.scanner.dedup import deduplicate


async def main():
    countries = ["Ghana", "Kenya"]
    print(f"=== Phase 1: Discovery ({', '.join(countries)}) ===")

    async def disc_progress(msg, current, total):
        print(f"  [{current}/{total}] {msg}")

    raw = await discover_opportunities(countries, on_progress=disc_progress)
    print(f"\nDiscovered: {len(raw)} raw results\n")

    print("=== Phase 2: Analysis (Claude) ===")

    async def analysis_progress(msg, current, total):
        print(f"  [{current}/{total}] {msg}")

    scored = await analyze_opportunities(raw, on_progress=analysis_progress)
    print(f"\nScored: {len(scored)} results\n")

    print("=== Phase 3: Deduplication ===")
    final = deduplicate(scored)
    print(f"After dedup: {len(final)} unique leads\n")

    print("=== Results Summary ===")
    active = [l for l in final if l.get("freshness") in ("active", "stale")]
    high = [l for l in final if (l.get("relevance_score") or 0) >= 70]
    urgent = [l for l in final if l.get("urgency") == "high"]

    print(f"  Total:    {len(final)}")
    print(f"  Active:   {len(active)}")
    print(f"  Score>=70: {len(high)}")
    print(f"  Urgent:   {len(urgent)}")

    print("\n=== Top 5 by Relevance ===")
    top5 = sorted(final, key=lambda l: l.get("relevance_score", 0), reverse=True)[:5]
    for l in top5:
        print(f"  [{l.get('relevance_score'):>3}] [{l.get('freshness'):>8}] [{l.get('urgency'):>6}] {l.get('title', '')[:70]}")

    print("\n=== Full JSON ===")
    print(json.dumps(final, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
