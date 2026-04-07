from datetime import datetime

YEAR = datetime.now().year

QUERY_TEMPLATES = [
    "IFRS 9 ECL software tender procurement bank {country} {year}",
    "expected credit loss system RFQ microfinance bank {country} {year}",
    "IFRS 9 implementation compliance deadline bank {country} {year}",
    "credit risk provisioning software procurement {country} {year}",
    "IFRS 9 ECL tool bid request financial institution {country} {year}",
]


def generate_queries(countries: list[str]) -> list[dict]:
    """Generate search queries for a list of countries."""
    queries = []
    for country in countries:
        for i, tpl in enumerate(QUERY_TEMPLATES[:2]):  # 2 queries per country
            queries.append({
                "query": tpl.format(country=country, year=YEAR),
                "country": country,
                "template_id": i,
            })
    return queries
