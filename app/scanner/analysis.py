import json
import re
import logging
from datetime import date
from typing import Callable, Awaitable

import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

aclient = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

BATCH_SIZE = 12

ANALYSIS_PROMPT_TEMPLATE = """You are a business analyst for Delphee, an IFRS 9 ECL calculator \
for small/mid-size banks, MFIs, and DFIs in developing markets. \
Delphee is affordable, cloud-native, and simple (no deep statistical expertise needed).

TODAY: {today}

Analyze these raw opportunities and for EACH one, produce a scored assessment.

FRESHNESS RULES:
- "active": published <6 months ago OR has a future deadline
- "stale": 6-12 months old, no clear deadline
- "outdated": >12 months old, no future dates
- "expired": deadline already passed
- "unknown": no dates found

SCORING (0-100 relevance to Delphee):
- Active tenders/RFQs explicitly for ECL/IFRS 9 software: 70-100
- Regulatory news forcing IFRS 9 adoption (new market opportunity): 50-75
- General credit risk / provisioning tenders (may need ECL tool): 40-65
- News/consulting not directly requiring a tool: 20-45
- Cap expired or outdated results at 40

URGENCY:
- "high": active with deadline <30 days away
- "medium": active with deadline 30-90 days, or stale with strong relevance
- "low": everything else

FOLLOW-UP ACTION: short, specific recommendation (e.g., "Submit proposal by deadline", \
"Contact procurement officer", "Monitor for RFQ release", "Share Delphee case study").

Return ONLY a valid JSON array with these fields per item:
title, institution, country, type, summary, relevance_score (int), relevance_reason,
deadline (ISO date or null), published_date (ISO date or null), freshness, freshness_reason,
contact_info (or null), follow_up_action, source_url (or null), urgency

If nothing is relevant, return: []"""


async def analyze_opportunities(
    raw_results: list[dict],
    on_progress: Callable[[str, int, int], Awaitable[None]] | None = None,
) -> list[dict]:
    """Use Claude to score, classify, and enrich raw discovery results."""
    if not raw_results:
        return []

    today = date.today().isoformat()
    prompt_base = ANALYSIS_PROMPT_TEMPLATE.format(today=today)

    batches = [raw_results[i:i + BATCH_SIZE] for i in range(0, len(raw_results), BATCH_SIZE)]
    scored: list[dict] = []

    for idx, batch in enumerate(batches):
        if on_progress:
            await on_progress(f"Analyzing batch {idx + 1}/{len(batches)}", idx + 1, len(batches))

        # Strip long redirect URLs before sending to Claude — keeps prompt compact.
        # source_url is preserved from the original raw_results and written to the DB separately.
        compact_batch = [
            {k: v for k, v in item.items() if k != "source_url"} for item in batch
        ]
        user_msg = f"{prompt_base}\n\nRAW OPPORTUNITIES:\n{json.dumps(compact_batch, indent=2)}"

        try:
            response = await aclient.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                messages=[{"role": "user", "content": user_msg}],
            )
            try:
                from app.usage_tracker import record_claude
                record_claude(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
            except Exception:
                pass
            text = response.content[0].text if response.content else ""
            parsed = _parse_json_array(text)

            # Restore source_url from original raw results (matched by position)
            for i, item in enumerate(parsed):
                if i < len(batch) and not item.get("source_url"):
                    item["source_url"] = batch[i].get("source_url")

            scored.extend(parsed)
            logger.info("Analysis batch %d/%d: scored %d results", idx + 1, len(batches), len(parsed))

        except Exception as e:
            logger.error("Analysis error on batch %d: %s", idx + 1, e)
            if on_progress:
                await on_progress(f"Analysis error: {e}", idx + 1, len(batches))

    return scored


def _parse_json_array(text: str) -> list[dict]:
    """Safely extract a JSON array from model output."""
    clean = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\[[\s\S]*\]", clean)
    if match:
        try:
            parsed = json.loads(match.group())
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            pass
    return []
