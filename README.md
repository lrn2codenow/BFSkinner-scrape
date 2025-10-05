# BFSkinner-scrape

Command line scraper that crawls [bfskinner.org](https://www.bfskinner.org/) for
links to freely available resources such as PDFs, audio, and other downloads.

## Prerequisites

- Python 3.12+
- Recommended: create a virtual environment and install dependencies from
  `requirements.txt`.

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python scrape.py --max-pages 300 --delay 1.0 --output data/free_resources.csv \
  --json data/free_resources.json
```

The script performs a breadth-first crawl of `bfskinner.org`, recording resource
links that either point to downloadable assets (PDFs, audio, etc.) or pages with
keywords indicating free materials. Results are written to CSV and optionally
JSON files.

> **Note**
> Access to external websites may be restricted in certain network
> environments. If the crawl logs proxy-related errors (e.g. 403 responses), try
> running the script from a network with unrestricted outbound HTTPS access.

## Development

- `scrape.py` exposes the CLI entry point.
- Core scraping logic lives in `bfskinner_scraper/scraper.py`.
- The scraper returns a list of `ResourceRecord` dataclasses that can be easily
  converted to pandas DataFrames via `BFSkinnerScraper.to_dataframe`.

## Exporting to Pandas

```python
from bfskinner_scraper import BFSkinnerScraper

scraper = BFSkinnerScraper(max_pages=150)
resources = scraper.crawl()
df = scraper.to_dataframe(resources)
df.to_excel("data/free_resources.xlsx", index=False)
```
