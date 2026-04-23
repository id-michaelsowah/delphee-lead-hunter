import json
import logging
import os
import re

import anthropic
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

aclient = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
gclient = genai.Client(api_key=settings.gemini_api_key)

_TIERS_FILE = os.path.join(os.path.dirname(__file__), "market_tiers.json")

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_market_tier(country: str) -> str:
    tiers = _load_json(_TIERS_FILE)
    if country in tiers.get("core", []):
        return "core"
    if country in tiers.get("expansion", []):
        return "expansion"
    return "greenfield"


# ── Phase 1: Gemini discovers raw institution data via Google Search ──────────

DISCOVERY_PROMPT = """Search the web thoroughly for regulated financial institutions in {country} \
that may need IFRS 9 / ECL software. Your goal is to find AT LEAST 15-20 candidate institutions \
— cast a wide net. Search multiple sources: the central bank registry, DFI portfolio pages \
(IFC, FMO, AfDB, Norfund, etc.), MIX Market, financial databases, news articles, and annual \
reports. Do not stop after finding a few obvious names — look for smaller or less prominent \
institutions too. Focus on:
- Licensed commercial banks and regulated microfinance institutions (MFIs)
- Institutions with any international investors, lenders, or shareholders, including: \
multilateral DFIs (IFC, AfDB, EBRD, ADB, EIB); bilateral DFIs (FMO, DEG, Proparco, BIO, \
DFC, BII, Norfund, Swedfund, OeEB, COFIDES); impact investors and development-focused PE \
(BlueOrchard, responsAbility, Symbiotics, AbleNordic, BlueEarth Capital, Helios Investment \
Partners, Amethis, Development Partners International, Investisseurs & Partenaires); \
international commercial banks or foreign institutional investors holding equity or debt; \
or any other foreign shareholder, lender, or guarantor
- Institutions with retail, SME, or microfinance lending books
- Central bank registry, DFI portfolio disclosures, annual reports, financial databases

For each institution found, extract:
- institution_name: full legal name
- type: one of commercial_bank, microfinance_institution, development_finance_institution, cooperative_bank
- ownership_summary: brief description of ownership structure
- shareholders: list of international entities that hold equity in this institution \
(e.g. IFC equity stake, Norfund shareholding, foreign bank ownership). Search the annual \
report shareholder register, central bank ownership disclosures, and DFI portfolio pages.
- international_stakeholders: list of international entities that have a lending, guarantee, \
or non-equity relationship with this institution (e.g. IFC loan, FMO credit line, EBRD guarantee). \
Do NOT duplicate entities already listed in shareholders.
- estimated_asset_size: total assets expressed as both the original currency value AND its EUR equivalent \
(e.g. "USD 120M (~EUR 110M)"). Search the institution's latest annual report, central bank registry, \
MIX Market, financial databases, or any regulatory filing to find this figure. Use the current \
approximate exchange rate to compute the EUR equivalent. If after searching you genuinely cannot \
find any asset size data, set this to null — do not guess.
- auditor: name of external auditor if available, else null
- ifrs9_status: one of adopted, in_progress, not_yet, unknown
- source_url: direct URL to the source of this information
- notes: any other relevant details

Return ONLY a valid JSON array. No markdown, no explanation."""


async def _gemini_search(country: str) -> list[dict]:
    prompt = DISCOVERY_PROMPT.format(country=country)
    for model in GEMINI_MODELS:
        try:
            response = await gclient.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2,
                ),
            )
            text = response.text or ""
            try:
                from app.usage_tracker import record_gemini
                um = response.usage_metadata
                if um:
                    record_gemini(
                        input_tokens=um.prompt_token_count or 0,
                        output_tokens=um.candidates_token_count or 0,
                    )
            except Exception:
                pass
            results = _parse_json_array(text)
            logger.info("Gemini found %d raw institutions in %s", len(results), country)
            return results
        except Exception as e:
            err = str(e)
            if "404" in err:
                logger.warning("Model %s not available (404), trying next...", model)
                continue
            logger.error("Gemini institution search error for %s: %s", country, e)
            return []
    logger.error("All Gemini models exhausted for institution search in %s", country)
    return []


# ── Phase 2: Claude filters raw results against criteria ──────────────────────

FILTER_PROMPT = """You are a financial sector analyst helping Delphee, an IFRS 9 ECL \
software provider for small/mid-size banks, MFIs, and DFIs in developing markets.

A sales lead has been identified in {country}:
- Lead type: {lead_type}
- Lead summary: {lead_summary}
- Relevance to Delphee: {relevance_reason}

Below are raw institution records found via web search in {country}. \
Your task: filter and rank these to return the TOP 10 most promising Delphee targets.

MUST-HAVE (hard filters — exclude institutions that fail any of these):
1. Must have international investors, lenders, or shareholders — this includes multilateral DFIs \
(IFC, AfDB, EBRD, ADB, EIB), bilateral DFIs (FMO, DEG, Proparco, BII, Norfund, Swedfund, OeEB), \
impact investors (BlueOrchard, responsAbility, AbleNordic, BlueEarth Capital, Symbiotics), \
development-focused private equity (Helios, Amethis, Development Partners International), \
or any foreign equity/debt stakeholder
2. Must NOT be fully state-owned with no international stakeholders
3. Must NOT be a subsidiary or member of a larger banking group
4. Total assets must be at least EUR 20 million equivalent. The estimated_asset_size field should \
include a EUR equivalent — use that for comparison. If asset size is null (not found), do not \
automatically disqualify; use other signals to judge whether the institution is likely above the threshold.
5. Must be a regulated licensed commercial bank or regulated MFI
6. Must have a lending-heavy business model with retail, SME, or microfinance exposure \
(exclude pure corporate/wholesale lenders)

RANKING BOOSTS (prefer but do not require):
- Audited by a Big 4 firm (Deloitte, PwC, EY, KPMG)
- Country has a recent or upcoming IFRS 9 regulatory deadline
- DFI-backed (DFI covenants often require IFRS 9 compliance)

RAW INSTITUTION DATA:
{raw_data}

Return ONLY a valid JSON array of the top 10 qualifying institutions. \
Each item must have ALL of these fields:
- institution_name (string)
- country (string — always "{country}")
- type (commercial_bank | microfinance_institution | development_finance_institution | cooperative_bank)
- ownership_summary (string)
- shareholders (list of strings — international equity investors/owners only)
- international_stakeholders (list of strings — international lenders, guarantors, or non-equity stakeholders only; no overlap with shareholders)
- dfi_backed (boolean)
- estimated_asset_size (string or null)
- business_model_summary (string: 1 sentence)
- lending_focus (list of strings e.g. ["SME", "microfinance", "retail"])
- auditor (string or null)
- big4_audited (boolean or null)
- ifrs9_status (adopted | in_progress | not_yet | unknown)
- source_url (string or null)
- relevance_notes (string: 1-2 sentences on why this is a strong Delphee target)

If fewer than 10 qualify, return only those that do. If none qualify, return [].
Return ONLY the JSON array. No markdown, no explanation."""


async def _claude_filter(raw: list[dict], lead: dict, country: str) -> list[dict]:
    prompt = FILTER_PROMPT.format(
        country=country,
        lead_type=lead.get("type", "unknown"),
        lead_summary=lead.get("summary", ""),
        relevance_reason=lead.get("relevance_reason", ""),
        raw_data=json.dumps(raw, indent=2),
    )
    try:
        response = await aclient.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
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
        results = _parse_json_array(text)
        logger.info("Claude filtered to %d qualifying institutions in %s", len(results), country)
        return results
    except Exception as e:
        logger.error("Claude filter error for %s: %s", country, e)
        return []


# ── Public entry point ────────────────────────────────────────────────────────

async def find_target_institutions(lead: dict) -> list[dict]:
    """Gemini searches for institutions, Claude filters against criteria. Returns top 10."""
    country = lead.get("country", "")
    if not country:
        return []

    # Phase 1: web search
    raw = await _gemini_search(country)
    if not raw:
        logger.warning("No raw institutions found by Gemini for %s", country)
        return []

    # Phase 2: filter and rank
    institutions = await _claude_filter(raw, lead, country)

    # Phase 3: resolve Gemini grounding redirect URLs before storage
    from app.scanner.resolve_urls import resolve_urls
    institutions = await resolve_urls(institutions)

    # Enrich with lead linkage, market tier, and lead summary fields
    tier = get_market_tier(country)
    for inst in institutions:
        inst["lead_id"] = lead.get("id")
        inst["scan_run_id"] = lead.get("scan_run_id")
        inst["market_tier"] = tier
        inst["lead_title"] = lead.get("title")
        inst["lead_type"] = lead.get("type")
        inst.setdefault("country", country)

    return institutions


def _parse_json_array(text: str) -> list[dict]:
    clean = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\[[\s\S]*\]", clean)
    if match:
        try:
            parsed = json.loads(match.group())
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            pass
    return []
