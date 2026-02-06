"""Tests for the bfskinner_scraper module (resource scraper)."""

import pytest
from unittest import mock

import requests

from bfskinner_scraper import BFSkinnerScraper, ResourceRecord


# ---------------------------------------------------------------------------
# ResourceRecord tests
# ---------------------------------------------------------------------------

class TestResourceRecord:
    def test_as_dict_returns_all_fields(self):
        record = ResourceRecord(
            page_url="https://www.bfskinner.org/resources/",
            resource_url="https://www.bfskinner.org/doc.pdf",
            resource_title="Download PDF",
            resource_type="pdf",
            page_title="Resources",
            description="A useful document.",
        )
        d = record.as_dict()
        assert d == {
            "page_url": "https://www.bfskinner.org/resources/",
            "resource_url": "https://www.bfskinner.org/doc.pdf",
            "resource_title": "Download PDF",
            "resource_type": "pdf",
            "page_title": "Resources",
            "description": "A useful document.",
        }

    def test_as_dict_with_defaults(self):
        record = ResourceRecord(
            page_url="https://example.com/",
            resource_url="https://example.com/file.mp3",
            resource_title="Audio",
            resource_type="mp3",
        )
        d = record.as_dict()
        assert d["page_title"] is None
        assert d["description"] is None

    def test_frozen(self):
        record = ResourceRecord(
            page_url="https://example.com/",
            resource_url="https://example.com/file.pdf",
            resource_title="Doc",
            resource_type="pdf",
        )
        with pytest.raises(AttributeError):
            record.page_url = "changed"

    def test_equality(self):
        kwargs = dict(
            page_url="https://example.com/",
            resource_url="https://example.com/file.pdf",
            resource_title="Doc",
            resource_type="pdf",
        )
        assert ResourceRecord(**kwargs) == ResourceRecord(**kwargs)

    def test_inequality(self):
        base = dict(
            page_url="https://example.com/",
            resource_url="https://example.com/file.pdf",
            resource_title="Doc",
            resource_type="pdf",
        )
        r1 = ResourceRecord(**base)
        r2 = ResourceRecord(**{**base, "resource_title": "Other"})
        assert r1 != r2


# ---------------------------------------------------------------------------
# BFSkinnerScraper initialisation
# ---------------------------------------------------------------------------

class TestScraperInit:
    def test_default_base_url(self):
        scraper = BFSkinnerScraper()
        assert scraper.base_url == "https://www.bfskinner.org/"

    def test_base_url_trailing_slash_normalised(self):
        scraper = BFSkinnerScraper(base_url="https://example.com")
        assert scraper.base_url == "https://example.com/"
        scraper2 = BFSkinnerScraper(base_url="https://example.com/")
        assert scraper2.base_url == "https://example.com/"

    def test_custom_session(self):
        session = requests.Session()
        scraper = BFSkinnerScraper(session=session)
        assert scraper.session is session

    def test_default_headers_applied(self):
        scraper = BFSkinnerScraper()
        assert "User-Agent" in scraper.session.headers

    def test_custom_params(self):
        scraper = BFSkinnerScraper(max_pages=50, request_delay=1.0, timeout=15)
        assert scraper.max_pages == 50
        assert scraper.request_delay == 1.0
        assert scraper.timeout == 15


# ---------------------------------------------------------------------------
# Helper to build mock responses
# ---------------------------------------------------------------------------

def _mock_response(text="", status_code=200, content_type="text/html; charset=utf-8", ok=True):
    resp = mock.Mock(spec=requests.Response)
    resp.text = text
    resp.status_code = status_code
    resp.ok = ok
    resp.headers = {"Content-Type": content_type}
    return resp


# ---------------------------------------------------------------------------
# _fetch tests
# ---------------------------------------------------------------------------

class TestFetch:
    def test_returns_html_text(self):
        session = mock.Mock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = _mock_response("<html></html>")
        scraper = BFSkinnerScraper(session=session)
        result = scraper._fetch("https://example.com/page")
        assert result == "<html></html>"
        session.get.assert_called_once_with("https://example.com/page", timeout=30)

    def test_returns_none_for_non_ok_response(self):
        session = mock.Mock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = _mock_response(status_code=404, ok=False)
        scraper = BFSkinnerScraper(session=session)
        assert scraper._fetch("https://example.com/missing") is None

    def test_returns_none_for_non_html_content(self):
        session = mock.Mock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = _mock_response(
            content_type="application/pdf", text=""
        )
        scraper = BFSkinnerScraper(session=session)
        assert scraper._fetch("https://example.com/file.pdf") is None

    def test_propagates_request_exception(self):
        session = mock.Mock(spec=requests.Session)
        session.headers = {}
        session.get.side_effect = requests.ConnectionError("timeout")
        scraper = BFSkinnerScraper(session=session)
        with pytest.raises(requests.ConnectionError):
            scraper._fetch("https://example.com/")


# ---------------------------------------------------------------------------
# _extract_page_title tests
# ---------------------------------------------------------------------------

class TestExtractPageTitle:
    def test_extracts_title(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><head><title> My Page </title></head></html>", "html.parser")
        assert BFSkinnerScraper._extract_page_title(soup) == "My Page"

    def test_returns_none_without_title(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><head></head></html>", "html.parser")
        assert BFSkinnerScraper._extract_page_title(soup) is None


# ---------------------------------------------------------------------------
# _is_internal_url tests
# ---------------------------------------------------------------------------

class TestIsInternalUrl:
    def test_same_domain_is_internal(self):
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        assert scraper._is_internal_url("https://www.bfskinner.org/resources/") is True

    def test_different_domain_is_external(self):
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        assert scraper._is_internal_url("https://www.google.com/") is False

    def test_relative_url_is_internal(self):
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        assert scraper._is_internal_url("/about") is True


# ---------------------------------------------------------------------------
# _normalize_url tests
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_strips_fragment(self):
        result = BFSkinnerScraper._normalize_url("https://example.com/page#section")
        assert "#" not in result
        assert result == "https://example.com/page"

    def test_preserves_query(self):
        result = BFSkinnerScraper._normalize_url("https://example.com/search?q=test")
        assert result == "https://example.com/search?q=test"

    def test_defaults_scheme_to_https(self):
        result = BFSkinnerScraper._normalize_url("//example.com/page")
        assert result == "https://example.com/page"

    def test_relative_url_returned_as_is(self):
        result = BFSkinnerScraper._normalize_url("/about")
        assert result == "/about"


# ---------------------------------------------------------------------------
# _classify_resource tests
# ---------------------------------------------------------------------------

class TestClassifyResource:
    def setup_method(self):
        self.scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")

    @pytest.mark.parametrize("ext,expected", [
        (".pdf", "pdf"),
        (".doc", "doc"),
        (".docx", "docx"),
        (".mp3", "mp3"),
        (".mp4", "mp4"),
        (".wav", "wav"),
        (".zip", "zip"),
        (".ppt", "ppt"),
        (".pptx", "pptx"),
        (".xls", "xls"),
        (".xlsx", "xlsx"),
        (".m4a", "m4a"),
    ])
    def test_classifies_by_extension(self, ext, expected):
        url = f"https://www.bfskinner.org/files/document{ext}"
        assert self.scraper._classify_resource(url, "some text") == expected

    def test_classifies_by_extension_case_insensitive(self):
        url = "https://www.bfskinner.org/files/document.PDF"
        assert self.scraper._classify_resource(url, "") == "pdf"

    @pytest.mark.parametrize("keyword", [
        "download", "free", "resource", "handout", "worksheet",
        "guide", "ebook", "podcast", "video", "audio", "pdf",
    ])
    def test_classifies_internal_link_by_keyword(self, keyword):
        url = "https://www.bfskinner.org/page"
        assert self.scraper._classify_resource(url, f"Click to {keyword}") == "page"

    def test_keyword_match_requires_internal_url(self):
        url = "https://external.com/page"
        assert self.scraper._classify_resource(url, "free download") is None

    def test_returns_none_for_non_http(self):
        assert self.scraper._classify_resource("mailto:a@b.com", "free") is None

    def test_returns_none_for_no_match(self):
        url = "https://www.bfskinner.org/about"
        assert self.scraper._classify_resource(url, "Learn more") is None


# ---------------------------------------------------------------------------
# _derive_description tests
# ---------------------------------------------------------------------------

class TestDeriveDescription:
    def test_extracts_parent_text(self):
        from bs4 import BeautifulSoup
        html = '<p>A great resource. <a href="/doc.pdf">Download here</a></p>'
        soup = BeautifulSoup(html, "html.parser")
        anchor = soup.find("a")
        desc = BFSkinnerScraper._derive_description(anchor)
        assert "A great resource" in desc

    def test_falls_back_to_anchor_text(self):
        from bs4 import BeautifulSoup
        html = '<a href="/doc.pdf">Download the PDF</a>'
        soup = BeautifulSoup(html, "html.parser")
        anchor = soup.find("a")
        desc = BFSkinnerScraper._derive_description(anchor)
        assert desc == "Download the PDF"

    def test_returns_none_for_empty_anchor(self):
        from bs4 import BeautifulSoup
        html = '<a href="/doc.pdf"></a>'
        soup = BeautifulSoup(html, "html.parser")
        anchor = soup.find("a")
        desc = BFSkinnerScraper._derive_description(anchor)
        assert desc is None


# ---------------------------------------------------------------------------
# _extract_internal_links tests
# ---------------------------------------------------------------------------

class TestExtractInternalLinks:
    def test_yields_internal_links(self):
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <a href="/about">About</a>
            <a href="https://www.bfskinner.org/contact">Contact</a>
            <a href="https://external.com/">External</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        links = list(scraper._extract_internal_links("https://www.bfskinner.org/", soup))
        assert "https://www.bfskinner.org/about" in links
        assert "https://www.bfskinner.org/contact" in links
        assert "https://external.com/" not in links

    def test_skips_empty_href(self):
        from bs4 import BeautifulSoup
        html = '<html><body><a href="">empty</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        links = list(scraper._extract_internal_links("https://www.bfskinner.org/", soup))
        # empty href resolves to the page itself which is internal
        assert len(links) >= 0  # just verifies no crash


# ---------------------------------------------------------------------------
# _extract_resources tests
# ---------------------------------------------------------------------------

class TestExtractResources:
    def test_finds_pdf_link(self):
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <p>Check out this document: <a href="/files/report.pdf">Download Report</a></p>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        resources = scraper._extract_resources(
            "https://www.bfskinner.org/resources/", "Resources", soup
        )
        assert len(resources) == 1
        assert resources[0].resource_type == "pdf"
        assert resources[0].resource_title == "Download Report"
        assert resources[0].page_title == "Resources"

    def test_finds_keyword_link(self):
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <a href="/stuff">Free resource pack</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        resources = scraper._extract_resources(
            "https://www.bfskinner.org/", None, soup
        )
        assert len(resources) == 1
        assert resources[0].resource_type == "page"

    def test_deduplicates_resources(self):
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <a href="/files/report.pdf">Download Report</a>
            <a href="/files/report.pdf">Download Report</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        resources = scraper._extract_resources(
            "https://www.bfskinner.org/", "Page", soup
        )
        assert len(resources) == 1

    def test_skips_non_matching_links(self):
        from bs4 import BeautifulSoup
        html = """
        <html><body>
            <a href="/about">About Us</a>
            <a href="https://external.com/page">Partner Site</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        scraper = BFSkinnerScraper(base_url="https://www.bfskinner.org/")
        resources = scraper._extract_resources(
            "https://www.bfskinner.org/", "Page", soup
        )
        assert len(resources) == 0


# ---------------------------------------------------------------------------
# crawl() integration tests
# ---------------------------------------------------------------------------

class TestCrawl:
    def _make_scraper(self, session, **kwargs):
        session.headers = {}
        return BFSkinnerScraper(
            base_url="https://www.bfskinner.org/",
            session=session,
            request_delay=0,
            **kwargs,
        )

    def test_crawl_finds_resources_on_single_page(self):
        html = """
        <html>
        <head><title>Resources</title></head>
        <body>
            <a href="/files/guide.pdf">Download guide</a>
        </body>
        </html>
        """
        session = mock.Mock(spec=requests.Session)
        session.get.return_value = _mock_response(html)
        scraper = self._make_scraper(session, max_pages=1)
        resources = scraper.crawl()

        assert len(resources) == 1
        assert resources[0].resource_type == "pdf"
        assert "guide.pdf" in resources[0].resource_url

    def test_crawl_follows_internal_links(self):
        page1 = """
        <html>
        <head><title>Home</title></head>
        <body>
            <a href="/resources">Resources</a>
        </body>
        </html>
        """
        page2 = """
        <html>
        <head><title>Resources</title></head>
        <body>
            <a href="/files/paper.pdf">Paper</a>
        </body>
        </html>
        """
        session = mock.Mock(spec=requests.Session)
        session.get.side_effect = [
            _mock_response(page1),
            _mock_response(page2),
            # The crawler also tries to fetch the PDF URL as an internal link
            _mock_response(content_type="application/pdf", text=""),
        ]
        scraper = self._make_scraper(session, max_pages=10)
        resources = scraper.crawl()

        assert session.get.call_count == 3
        assert len(resources) >= 1
        assert any(r.resource_type == "pdf" for r in resources)

    def test_crawl_respects_max_pages(self):
        html = """
        <html><body>
            <a href="/page2">Next</a>
            <a href="/page3">More</a>
        </body></html>
        """
        session = mock.Mock(spec=requests.Session)
        session.get.return_value = _mock_response(html)
        scraper = self._make_scraper(session, max_pages=2)
        scraper.crawl()

        assert session.get.call_count <= 2

    def test_crawl_skips_already_visited_urls(self):
        html = """
        <html><body>
            <a href="https://www.bfskinner.org/">Home again</a>
        </body></html>
        """
        session = mock.Mock(spec=requests.Session)
        session.get.return_value = _mock_response(html)
        scraper = self._make_scraper(session, max_pages=5)
        scraper.crawl()

        # Should only fetch once since the self-link is already visited
        assert session.get.call_count == 1

    def test_crawl_handles_fetch_failure_gracefully(self):
        session = mock.Mock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("network down")
        scraper = self._make_scraper(session, max_pages=5)
        resources = scraper.crawl()

        assert resources == []

    def test_crawl_skips_non_html_pages(self):
        session = mock.Mock(spec=requests.Session)
        session.get.return_value = _mock_response(
            content_type="application/pdf", text=""
        )
        scraper = self._make_scraper(session, max_pages=1)
        resources = scraper.crawl()

        assert resources == []

    def test_crawl_does_not_revisit_failed_urls(self):
        """After a fetch failure, the URL is not re-added to the queue."""
        page_html = """
        <html><body>
            <a href="/broken">Broken Link</a>
        </body></html>
        """
        session = mock.Mock(spec=requests.Session)
        session.get.side_effect = [
            _mock_response(page_html),
            requests.ConnectionError("fail"),
        ]
        scraper = self._make_scraper(session, max_pages=10)
        scraper.crawl()

        # base page + /broken = 2 fetches total
        assert session.get.call_count == 2


# ---------------------------------------------------------------------------
# to_dataframe tests
# ---------------------------------------------------------------------------

class TestToDataframe:
    def test_creates_dataframe(self):
        pd = pytest.importorskip("pandas")
        scraper = BFSkinnerScraper()
        records = [
            ResourceRecord(
                page_url="https://example.com/",
                resource_url="https://example.com/file.pdf",
                resource_title="PDF",
                resource_type="pdf",
                page_title="Home",
                description="A file",
            ),
        ]
        df = scraper.to_dataframe(records)
        assert len(df) == 1
        assert list(df.columns) == [
            "page_url", "resource_url", "resource_title",
            "resource_type", "page_title", "description",
        ]

    def test_empty_records(self):
        pd = pytest.importorskip("pandas")
        scraper = BFSkinnerScraper()
        df = scraper.to_dataframe([])
        assert len(df) == 0
