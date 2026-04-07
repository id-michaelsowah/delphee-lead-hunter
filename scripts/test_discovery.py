"""
Standalone test for the Gemini discovery module.
Usage: python scripts/test_discovery.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv()

from app.scanner.discovery import discover_opportunities


async def main():
    print("Testing discovery with Ghana and Kenya...")

    async def progress(msg, current, total):
        print(f"  [{current}/{total}] {msg}")

    results = await discover_opportunities(["Ghana", "Kenya"], on_progress=progress)

    print(f"\nFound {len(results)} raw results:\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
