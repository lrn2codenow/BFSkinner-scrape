"""Scraper implementation for B.F. Skinner related content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


DEFAULT_USER_AGENT = "BFSkinnerScraper/1.0"
DEFAULT_TIMEOUT = 10


class ScraperError(RuntimeError):
    """Raised when the scraper cannot complete an operation."""


@dataclass(frozen=True)
class ArticleRecord:
    """Represents a single article discovered by the scraper."""

    title: str
    url: str
    summary: Optional[str] = None
    published: Optional[str] = None


class Scraper:
    """High level interface to fetch and parse paginated article listings."""

    def __init__(
        self,
        base_url: str,
        *,
        opener: Optional[urllib.request.OpenerDirector] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not base_url:
            raise ValueError("base_url must be provided")

        self.base_url = base_url
        self._opener = opener
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout

    # ------------------------------------------------------------------
    def scrape(self, *, start_url: Optional[str] = None) -> List[ArticleRecord]:
        """Collect article records across any paginated listing pages.

        Args:
            start_url: Optional explicit starting URL. Defaults to ``base_url``.

        Returns:
            A list of :class:`ArticleRecord` objects sorted in the order the
            articles were encountered.
        """

        next_page = start_url or self.base_url
        visited_pages = set()
        seen_articles = set()
        collected: List[ArticleRecord] = []

        while next_page and next_page not in visited_pages:
            visited_pages.add(next_page)
            html = self._fetch(next_page)
            articles, possible_next = self.parse_listing(html)

            for article in articles:
                if article.url in seen_articles:
                    continue
                seen_articles.add(article.url)
                collected.append(article)

            if not possible_next or possible_next in visited_pages:
                break
            next_page = possible_next

        return collected

    # ------------------------------------------------------------------
    def parse_listing(self, html: str) -> Tuple[List[ArticleRecord], Optional[str]]:
        """Parse an article listing page and extract article metadata.

        Args:
            html: The raw HTML payload for a listing page.

        Returns:
            A tuple of ``(articles, next_url)`` where ``next_url`` is ``None``
            when there is no pagination link.
        """

        root = self._parse_html(html)
        articles = self._extract_articles(root)
        next_url = self._find_next_link(root)
        return articles, next_url

    # ------------------------------------------------------------------
    def _fetch(self, url: str) -> str:
        """Retrieve HTML for the provided URL handling typical failures."""

        request = urllib.request.Request(url, headers=self.headers)
        opener = self._opener or urllib.request.build_opener()
        # Cache the opener for subsequent requests so tests can introspect call data.
        self._opener = opener

        try:
            with opener.open(request, timeout=self.timeout) as response:  # type: ignore[call-arg]
                charset = response.headers.get_content_charset() if response.headers else None
                encoding = charset or "utf-8"
                payload = response.read()
        except urllib.error.URLError as exc:  # pragma: no cover - integration detail
            raise ScraperError(f"Failed to fetch URL: {url}") from exc

        return payload.decode(encoding, errors="replace")

    # ------------------------------------------------------------------
    def _parse_html(self, html: str) -> ET.Element:
        try:
            return ET.fromstring(html)
        except ET.ParseError as exc:
            raise ScraperError("Unable to parse listing HTML") from exc

    # ------------------------------------------------------------------
    def _extract_articles(self, root: ET.Element) -> List[ArticleRecord]:
        articles: List[ArticleRecord] = []
        seen_urls = set()

        for article_el in root.findall(".//article"):
            title_el = article_el.find(".//h2")
            link_el = None
            if title_el is not None:
                link_el = title_el.find(".//a")

            if link_el is None:
                continue

            title = self._text_content(link_el) or self._text_content(title_el)
            href = (link_el.get("href") or "").strip()

            if not title or not href:
                continue

            url = urljoin(self.base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            summary_el = article_el.find(".//p")
            summary = self._text_content(summary_el)

            time_el = article_el.find(".//time")
            published = None
            if time_el is not None:
                published = (time_el.get("datetime") or self._text_content(time_el)) or None

            articles.append(
                ArticleRecord(
                    title=title,
                    url=url,
                    summary=summary or None,
                    published=published,
                )
            )

        return articles

    # ------------------------------------------------------------------
    def _find_next_link(self, root: ET.Element) -> Optional[str]:
        for link in root.findall(".//a"):
            rel = link.get("rel") or ""
            classes = link.get("class") or ""
            if self._contains_flag(rel, "next") or self._contains_flag(classes, "next"):
                href = (link.get("href") or "").strip()
                if href:
                    return urljoin(self.base_url, href)
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _contains_flag(attribute_value: str, flag: str) -> bool:
        tokens = [token.strip().lower() for token in attribute_value.split() if token.strip()]
        return flag.lower() in tokens

    # ------------------------------------------------------------------
    @staticmethod
    def _text_content(element: Optional[ET.Element]) -> str:
        if element is None:
            return ""
        parts: List[str] = [element.text or ""]
        for child in element:
            parts.append(Scraper._text_content(child))
            if child.tail:
                parts.append(child.tail)
        return "".join(parts).strip()
