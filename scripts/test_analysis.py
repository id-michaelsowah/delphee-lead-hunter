"""
Standalone test for the Claude analysis module.
Usage: python scripts/test_analysis.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.scanner.analysis import analyze_opportunities

FAKE_RAW = [
    {
        "title": "IFRS 9 ECL Software Procurement — Bank of Ghana",
        "institution": "Bank of Ghana",
        "country": "Ghana",
        "type": "tender",
        "summary": "The Bank of Ghana is seeking vendors to supply an Expected Credit Loss calculation system compliant with IFRS 9.",
        "published_date": "2026-02-15",
        "deadline": "2026-04-30",
        "source_url": "https://www.bog.gov.gh/tenders/ecl-system-2026",
        "contact_info": "procurement@bog.gov.gh",
    },
    {
        "title": "Kenya National Microfinance Bank Digital Transformation",
        "institution": "Kenya National Microfinance Bank",
        "country": "Kenya",
        "type": "rfq",
        "summary": "KNMB is requesting quotations for a cloud-based risk management and provisioning platform.",
        "published_date": "2025-06-01",
        "deadline": "2025-08-01",
        "source_url": "https://www.knmb.co.ke/rfq/risk-platform",
        "contact_info": None,
    },
    {
        "title": "IFRS 9 Mandatory Adoption — Central Bank of Nigeria Circular",
        "institution": "Central Bank of Nigeria",
        "country": "Nigeria",
        "type": "regulation",
        "summary": "CBN has issued a circular mandating all DMBs to achieve full IFRS 9 ECL compliance by Q1 2027.",
        "published_date": "2026-01-10",
        "deadline": None,
        "source_url": "https://www.cbn.gov.ng/circulars/ifrs9-2026",
        "contact_info": None,
    },
]


async def main():
    print("Testing Claude analysis on 3 fake results...")

    async def progress(msg, current, total):
        print(f"  [{current}/{total}] {msg}")

    results = await analyze_opportunities(FAKE_RAW, on_progress=progress)

    print(f"\nScored {len(results)} results:\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
