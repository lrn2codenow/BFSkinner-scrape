"""Tests for the scrape.py CLI entry point."""

import csv
import json
from pathlib import Path
from unittest import mock

import pytest

from scrape import export_csv, export_json, parse_args, main
from bfskinner_scraper import ResourceRecord


# ---------------------------------------------------------------------------
# parse_args tests
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self):
        with mock.patch("sys.argv", ["scrape.py"]):
            args = parse_args()
        assert args.output == Path("data/free_resources.csv")
        assert args.json_output is None
        assert args.max_pages == 200
        assert args.delay == 0.5
        assert args.log_level == "INFO"

    def test_custom_args(self):
        with mock.patch("sys.argv", [
            "scrape.py",
            "--output", "out.csv",
            "--json", "out.json",
            "--max-pages", "50",
            "--delay", "1.5",
            "--log-level", "DEBUG",
        ]):
            args = parse_args()
        assert args.output == Path("out.csv")
        assert args.json_output == Path("out.json")
        assert args.max_pages == 50
        assert args.delay == 1.5
        assert args.log_level == "DEBUG"


# ---------------------------------------------------------------------------
# export_csv tests
# ---------------------------------------------------------------------------

class TestExportCsv:
    def test_writes_csv_with_data(self, tmp_path):
        out = tmp_path / "result.csv"
        data = [
            {
                "page_url": "https://example.com/",
                "page_title": "Home",
                "resource_url": "https://example.com/file.pdf",
                "resource_title": "My PDF",
                "resource_type": "pdf",
                "description": "A file.",
            }
        ]
        export_csv(out, data)
        assert out.exists()

        with out.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["page_url"] == "https://example.com/"
        assert rows[0]["resource_title"] == "My PDF"

    def test_writes_empty_csv(self, tmp_path):
        out = tmp_path / "empty.csv"
        export_csv(out, [])
        assert out.exists()

        with out.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows == []

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "result.csv"
        export_csv(out, [])
        assert out.exists()


# ---------------------------------------------------------------------------
# export_json tests
# ---------------------------------------------------------------------------

class TestExportJson:
    def test_writes_json_with_data(self, tmp_path):
        out = tmp_path / "result.json"
        data = [
            {
                "page_url": "https://example.com/",
                "resource_url": "https://example.com/file.pdf",
                "resource_title": "PDF",
                "resource_type": "pdf",
                "page_title": "Home",
                "description": "desc",
            }
        ]
        export_json(out, data)
        assert out.exists()

        content = json.loads(out.read_text(encoding="utf-8"))
        assert len(content) == 1
        assert content[0]["resource_type"] == "pdf"

    def test_writes_empty_json(self, tmp_path):
        out = tmp_path / "empty.json"
        export_json(out, [])
        content = json.loads(out.read_text(encoding="utf-8"))
        assert content == []

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "nested" / "dir" / "result.json"
        export_json(out, [])
        assert out.exists()


# ---------------------------------------------------------------------------
# main() integration test
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_writes_csv_and_json(self, tmp_path):
        csv_path = tmp_path / "out.csv"
        json_path = tmp_path / "out.json"

        fake_records = [
            ResourceRecord(
                page_url="https://www.bfskinner.org/",
                resource_url="https://www.bfskinner.org/file.pdf",
                resource_title="Guide",
                resource_type="pdf",
                page_title="Home",
                description="A guide.",
            ),
        ]

        with mock.patch("sys.argv", [
            "scrape.py",
            "--output", str(csv_path),
            "--json", str(json_path),
            "--max-pages", "1",
        ]), mock.patch("scrape.BFSkinnerScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.crawl.return_value = fake_records
            instance.base_url = "https://www.bfskinner.org/"
            main()

        assert csv_path.exists()
        assert json_path.exists()

        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["resource_type"] == "pdf"

        content = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(content) == 1

    def test_main_csv_only(self, tmp_path):
        csv_path = tmp_path / "out.csv"

        with mock.patch("sys.argv", [
            "scrape.py",
            "--output", str(csv_path),
            "--max-pages", "1",
        ]), mock.patch("scrape.BFSkinnerScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.crawl.return_value = []
            instance.base_url = "https://www.bfskinner.org/"
            main()

        assert csv_path.exists()

    def test_main_no_resources(self, tmp_path):
        csv_path = tmp_path / "out.csv"

        with mock.patch("sys.argv", [
            "scrape.py",
            "--output", str(csv_path),
            "--max-pages", "1",
        ]), mock.patch("scrape.BFSkinnerScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.crawl.return_value = []
            instance.base_url = "https://www.bfskinner.org/"
            main()

        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows == []
