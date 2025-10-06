"""Command line entry point for scraping bfskinner.org free resources."""
from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Iterable

from bfskinner_scraper import BFSkinnerScraper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape free resources from https://www.bfskinner.org/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/free_resources.csv"),
        help="Path to the output CSV file (default: data/free_resources.csv)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        type=Path,
        help="Optional path to export the data as JSON",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Maximum number of pages to crawl (default: 200)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


def export_csv(path: Path, resources: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resources = list(resources)
    if not resources:
        logging.warning("No resources found; writing empty CSV to %s", path)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "page_url",
                "page_title",
                "resource_url",
                "resource_title",
                "resource_type",
                "description",
            ],
        )
        writer.writeheader()
        writer.writerows(resources)


def export_json(path: Path, resources: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as jsonfile:
        json.dump(list(resources), jsonfile, indent=2, ensure_ascii=False)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    scraper = BFSkinnerScraper(
        max_pages=args.max_pages,
        request_delay=args.delay,
    )

    logging.info(
        "Starting crawl of %s (max_pages=%s)", scraper.base_url, args.max_pages
    )
    resources = scraper.crawl()
    resource_dicts = [record.as_dict() for record in resources]

    export_csv(args.output, resource_dicts)
    if args.json_output:
        export_json(args.json_output, resource_dicts)

    logging.info("Scraping complete. %s resources captured.", len(resource_dicts))


if __name__ == "__main__":
    main()
