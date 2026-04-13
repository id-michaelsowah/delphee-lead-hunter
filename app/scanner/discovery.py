import json
import re
import asyncio
import logging
from typing import Callable, Awaitable

from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.gemini_api_key)

DISCOVERY_PROMPT_EN = """Search the web for IFRS 9 and ECL-related business opportunities \
in {countries}. Look for: tenders, RFQs, procurement notices, regulatory deadlines, \
news about banks needing ECL tools, consulting opportunities.

For each opportunity found, extract:
- title: short descriptive title
- institution: name of the bank, MFI, DFI, or regulatory body
- country: country name
- type: one of tender, rfq, news, regulation, consulting, partnership
- summary: 2-3 sentence description of the opportunity
- published_date: ISO date if found (YYYY-MM-DD), else null
- deadline: ISO date if found (YYYY-MM-DD), else null
- source_url: direct URL to the opportunity
- contact_info: email/phone/contact person if available, else null

Return ONLY a valid JSON array. No markdown fences, no preamble, no explanation."""

DISCOVERY_PROMPT_LOCAL = """Search the web in {language} for IFRS 9 and ECL-related business \
opportunities in {countries}. Focus specifically on locally-published sources: government \
procurement portals, central bank notices, local tender boards, and regional financial \
regulatory announcements. Many of these are only published in {language}.

For each opportunity found, extract:
- title: short descriptive title (translate to English)
- institution: name of the bank, MFI, DFI, or regulatory body
- country: country name
- type: one of tender, rfq, news, regulation, consulting, partnership
- summary: 2-3 sentence description in English
- published_date: ISO date if found (YYYY-MM-DD), else null
- deadline: ISO date if found (YYYY-MM-DD), else null
- source_url: direct URL to the opportunity
- contact_info: email/phone/contact person if available, else null

Return ONLY a valid JSON array. No markdown fences, no preamble, no explanation."""

# Countries where searching in a local language surfaces significantly more results
COUNTRY_LANGUAGES: dict[str, list[str]] = {
    # French — West Africa
    "Senegal": ["French"], "Côte d'Ivoire": ["French"], "Burkina Faso": ["French"],
    "Mali": ["French"], "Niger": ["French"], "Togo": ["French"], "Benin": ["French"],
    "Guinea": ["French"], "Guinea-Bissau": ["French"], "Mauritania": ["French"],
    # French — East Africa
    "Rwanda": ["French"], "Djibouti": ["French"], "Burundi": ["French"],
    # French — Central Africa
    "Cameroon": ["French"], "Chad": ["French"], "Gabon": ["French"],
    "Democratic Republic of Congo": ["French"], "Republic of Congo": ["French"],
    # French — Southern Africa
    "Madagascar": ["French"],
    # French — North Africa
    "Morocco": ["French"], "Tunisia": ["French"], "Algeria": ["French"],
    "Lebanon": ["French"],
    # Spanish — Latin America
    "Bolivia": ["Spanish"], "Honduras": ["Spanish"], "Guatemala": ["Spanish"],
    "Paraguay": ["Spanish"], "Ecuador": ["Spanish"], "Colombia": ["Spanish"],
    "Peru": ["Spanish"], "El Salvador": ["Spanish"], "Nicaragua": ["Spanish"],
    "Costa Rica": ["Spanish"],
    # Russian — Central Asia & Caucasus
    "Georgia": ["Russian"], "Armenia": ["Russian"], "Uzbekistan": ["Russian"],
    "Kyrgyzstan": ["Russian"], "Azerbaijan": ["Russian"],
    # Russian — Eastern Europe
    "Moldova": ["Russian"], "Ukraine": ["Russian"],
    "Bosnia and Herzegovina": ["Russian"], "Serbia": ["Russian"],
    "Montenegro": ["Russian"],
}

BATCH_SIZE = 3
BATCH_DELAY = 1.5  # seconds between batches
RETRY_DELAYS = [2, 4, 8]  # exponential backoff on 429

# Model fallback order — tries each in sequence if quota or availability fails.
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


async def discover_opportunities(
    countries: list[str],
    on_progress: Callable[[str, int, int], Awaitable[None]] | None = None,
) -> list[dict]:
    """Use Gemini with Google Search grounding to find raw opportunities."""
    batches = [countries[i:i + BATCH_SIZE] for i in range(0, len(countries), BATCH_SIZE)]
    all_results: list[dict] = []

    for idx, batch in enumerate(batches):
        country_str = ", ".join(batch)
        if on_progress:
            await on_progress(f"Searching: {country_str}", idx + 1, len(batches))

        # 1. English search for the whole batch
        prompt_en = DISCOVERY_PROMPT_EN.format(countries=country_str)
        parsed_en = await _search_with_retry(prompt_en, f"{country_str} [EN]")
        all_results.extend(parsed_en)
        logger.info("Batch %d/%d EN: found %d results for %s", idx + 1, len(batches), len(parsed_en), country_str)

        # 2. Per-language searches for countries that have local languages
        # Group countries by language so each language gets one focused request
        language_countries: dict[str, list[str]] = {}
        for country in batch:
            for lang in COUNTRY_LANGUAGES.get(country, []):
                language_countries.setdefault(lang, []).append(country)

        for language, lang_batch in language_countries.items():
            lang_country_str = ", ".join(lang_batch)
            prompt_local = DISCOVERY_PROMPT_LOCAL.format(
                language=language,
                countries=lang_country_str,
            )
            parsed_local = await _search_with_retry(prompt_local, f"{lang_country_str} [{language[:2].upper()}]")
            all_results.extend(parsed_local)
            logger.info("Batch %d/%d %s: found %d results for %s", idx + 1, len(batches), language, len(parsed_local), lang_country_str)
            await asyncio.sleep(BATCH_DELAY)

        if idx < len(batches) - 1:
            await asyncio.sleep(BATCH_DELAY)

    return all_results


async def _search_with_retry(prompt: str, label: str) -> list[dict]:
    for model in GEMINI_MODELS:
        result = await _try_model(prompt, label, model)
        if result is not None:
            return result
        logger.warning("Quota exhausted for model %s, trying next...", model)
    logger.error("All Gemini models exhausted for %s", label)
    return []


async def _try_model(prompt: str, label: str, model: str) -> list[dict] | None:
    """Try a single model with exponential backoff. Returns None if quota exhausted."""
    for attempt, delay in enumerate(RETRY_DELAYS + [None]):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2,
                ),
            )
            text = response.text or ""
            logger.info("Model %s succeeded for %s", model, label)
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
            return _parse_json_array(text)

        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                if delay is not None:
                    logger.warning("Rate limited on %s for %s, retrying in %ds...", model, label, delay)
                    await asyncio.sleep(delay)
                else:
                    return None  # Signal caller to try next model
            elif "404" in err_str:
                logger.warning("Model %s not available for %s (404), trying next model...", model, label)
                return None  # Signal caller to try next model
            else:
                logger.error("Discovery error on %s for %s: %s", model, label, e)
                return []  # Non-quota error — don't try other models

    return None


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
