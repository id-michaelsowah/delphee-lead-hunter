from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.85


def deduplicate(leads: list[dict], existing_titles: list[str] | None = None) -> list[dict]:
    """Remove duplicates within the batch and against existing DB titles."""
    seen: set[str] = set()
    all_existing: set[str] = {t.lower().strip() for t in (existing_titles or [])}
    unique: list[dict] = []

    for lead in leads:
        title = (lead.get("title") or "").lower().strip()
        inst = (lead.get("institution") or "").lower().strip()
        key = f"{title}|{inst}"

        # Exact dedup within current batch
        if key in seen:
            continue

        # Fuzzy match against existing DB titles
        is_dup = any(
            SequenceMatcher(None, title, existing).ratio() > SIMILARITY_THRESHOLD
            for existing in all_existing
        )

        if not is_dup:
            seen.add(key)
            all_existing.add(title)
            unique.append(lead)

    return unique
