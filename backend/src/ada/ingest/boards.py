"""Ingestion source configuration; every board verified live before inclusion."""

GREENHOUSE_BOARDS: dict[str, str] = {
    "moniepoint": "Moniepoint",
    "jumia": "Jumia",
    "oscar": "Oscar Health",
    "duolingo": "Duolingo",
    "guild": "Guild",
    "airbnb": "Airbnb",
    "sweetgreen": "Sweetgreen",
    "peloton": "Peloton",
    "instacart": "Instacart",
    "doordashusa": "DoorDash",
    "lyft": "Lyft",
    "stripe": "Stripe",
    "coinbase": "Coinbase",
    "gitlab": "GitLab",
    "canonical": "Canonical",
    "databricks": "Databricks",
    "mongodb": "MongoDB",
    "cloudflare": "Cloudflare",
    "reddit": "Reddit",
    "figma": "Figma",
    "twilio": "Twilio",
}

LEVER_COMPANIES: dict[str, str] = {
    "palantir": "Palantir",
    "spotify": "Spotify",
}

ASHBY_BOARDS: dict[str, str] = {
    "ramp": "Ramp",
    "linear": "Linear",
    "openai": "OpenAI",
    "notion": "Notion",
    "cursor": "Cursor",
    "replit": "Replit",
    "supabase": "Supabase",
}

JOOBLE_QUERIES: dict[str, list[tuple[str, str]]] = {
    "jooble.org": [
        ("remote software engineer", ""),
        ("remote customer support", ""),
        ("remote accountant", ""),
        ("remote data analyst", ""),
        ("remote virtual assistant", ""),
    ],
    "ng.jooble.org": [
        ("software engineer", "Lagos"),
        ("product manager", "Lagos"),
        ("data analyst", "Nigeria"),
        ("accountant", "Lagos"),
        ("nurse", "Nigeria"),
        ("sales representative", "Lagos"),
        ("customer service", "Lagos"),
        ("teacher", "Nigeria"),
        ("logistics", "Lagos"),
        ("administrative assistant", "Abuja"),
        ("engineer", "Port Harcourt"),
        ("banking", "Lagos"),
    ],
}
