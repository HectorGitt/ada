"""CLI entrypoint: python -m ada.ingest [--limit N]"""
import argparse
import asyncio

from ada.ingest.pipeline import run
from ada.observability import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, embed, and upsert job listings.")
    parser.add_argument("--limit", type=int, default=None, help="maximum listings to ingest")
    args = parser.parse_args()
    configure_logging()
    stats = asyncio.run(run(limit=args.limit))
    print(
        f"fetched={stats['fetched']} upserted={stats['upserted']} "
        f"embedded={stats['embedded']} total_in_db={stats['total']}"
    )


if __name__ == "__main__":
    main()
