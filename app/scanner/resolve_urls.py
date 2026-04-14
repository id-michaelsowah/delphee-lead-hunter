import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds per request
_CONCURRENCY = 10  # parallel HEAD requests


async def _resolve_one(client: httpx.AsyncClient, url: str) -> str:
    """Follow redirects and return the final URL. Returns original on any error."""
    if not url:
        return url
    try:
        r = await client.head(url, follow_redirects=True, timeout=_TIMEOUT)
        final = str(r.url)
        if final != url:
            logger.debug("Resolved %s → %s", url, final)
        return final
    except Exception:
        return url  # keep original if unreachable


async def resolve_urls(results: list[dict]) -> list[dict]:
    """Resolve redirect source_urls in parallel. Mutates and returns the list."""
    urls = [r.get("source_url") for r in results]
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def bounded(client: httpx.AsyncClient, url: str) -> str:
        async with sem:
            return await _resolve_one(client, url)

    async with httpx.AsyncClient() as client:
        resolved = await asyncio.gather(*[bounded(client, u) for u in urls])

    for result, final_url in zip(results, resolved):
        result["source_url"] = final_url

    return results
