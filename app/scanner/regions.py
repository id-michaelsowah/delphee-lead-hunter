import json
import os

_REGIONS_FILE = os.path.join(os.path.dirname(__file__), "regions.json")


def get_regions() -> dict[str, list[str]]:
    """Read regions from JSON file — always fresh, no restart needed."""
    with open(_REGIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


# Module-level constant for backwards compatibility (used by scanner pipeline)
REGIONS: dict[str, list[str]] = get_regions()
