"""Scraper implementation for bfskinner.org free resources."""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Iterable, Iterator, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResourceRecord:
    """Representation of a free resource discovered on the site."""

    page_url: str
    resource_url: str
    resource_title: str
    resource_type: str
    page_title: Optional[str] = None
    description: Optional[str] = None

    def as_dict(self) -> dict:
        """Return a dictionary representation suitable for serialization."""
        return asdict(self)


class BFSkinnerScraper:
    """Crawler that extracts free resources from bfskinner.org.

    The scraper performs a bounded breadth-first crawl across the domain, looking
    for downloadable assets (PDFs, audio/video files) and textual references to
    free resources.
    """

    RESOURCE_EXTENSIONS: Set[str] = {
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".zip",
        ".mp3",
        ".mp4",
        ".wav",
        ".m4a",
    }

    KEYWORD_HINTS: Set[str] = {
        "download",
        "free",
        "resource",
        "handout",
        "worksheet",
        "guide",
        "ebook",
        "podcast",
        "video",
        "audio",
        "pdf",
    }

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/117.0 Safari/537.36"
        )
    }

    def __init__(
        self,
        base_url: str = "https://www.bfskinner.org/",
        *,
        session: Optional[requests.Session] = None,
        max_pages: int = 200,
        request_delay: float = 0.5,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.session = session or requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.max_pages = max_pages
        self.request_delay = request_delay
        self.timeout = timeout
        self._visited: Set[str] = set()

    def crawl(self) -> List[ResourceRecord]:
        """Execute the crawl starting at ``base_url``."""
        queue: deque[str] = deque([self.base_url])
        resources: List[ResourceRecord] = []

        while queue and len(self._visited) < self.max_pages:
            url = queue.popleft()
            if url in self._visited:
                continue
            logger.debug("Fetching %s", url)
            try:
                html = self._fetch(url)
            except requests.RequestException as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                continue

            self._visited.add(url)
            if html is None:
                continue

            soup = BeautifulSoup(html, "html.parser")
            page_title = self._extract_page_title(soup)
            resources.extend(self._extract_resources(url, page_title, soup))

            for link in self._extract_internal_links(url, soup):
                if link not in self._visited and link not in queue:
                    queue.append(link)

            if self.request_delay:
                time.sleep(self.request_delay)

        return resources

    # ------------------------------------------------------------------
    def _fetch(self, url: str) -> Optional[str]:
        response = self.session.get(url, timeout=self.timeout)
        if not response.ok:
            logger.warning("Non-200 response for %s: %s", url, response.status_code)
            return None
        if "text/html" not in response.headers.get("Content-Type", ""):
            logger.debug("Skipping non-HTML content at %s", url)
            return None
        return response.text

    def _extract_internal_links(self, page_url: str, soup: BeautifulSoup) -> Iterator[str]:
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href:
                continue
            absolute = urljoin(page_url, href)
            if self._is_internal_url(absolute):
                cleaned = self._normalize_url(absolute)
                if cleaned:
                    yield cleaned

    def _extract_resources(
        self, page_url: str, page_title: Optional[str], soup: BeautifulSoup
    ) -> List[ResourceRecord]:
        resources: List[ResourceRecord] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            text = anchor.get_text(" ", strip=True)
            if not href:
                continue

            resource_url = urljoin(page_url, href)
            resource_type = self._classify_resource(resource_url, text)
            if resource_type is None:
                continue

            description = self._derive_description(anchor)
            record = ResourceRecord(
                page_url=self._normalize_url(page_url),
                resource_url=self._normalize_url(resource_url),
                resource_title=text or (page_title or ""),
                resource_type=resource_type,
                page_title=page_title,
                description=description,
            )
            if record not in resources:
                resources.append(record)
        return resources

    # ------------------------------------------------------------------
    def _classify_resource(self, resource_url: str, anchor_text: str) -> Optional[str]:
        parsed = urlparse(resource_url)
        if not parsed.scheme.startswith("http"):
            return None

        lower_path = parsed.path.lower()
        for ext in self.RESOURCE_EXTENSIONS:
            if lower_path.endswith(ext):
                return ext.lstrip(".")

        lower_text = (anchor_text or "").lower()
        if any(keyword in lower_text for keyword in self.KEYWORD_HINTS):
            if self._is_internal_url(resource_url):
                return "page"
        return None

    @staticmethod
    def _derive_description(anchor) -> Optional[str]:
        """Attempt to capture a short description near the anchor."""
        parent = anchor.find_parent(["p", "li", "div"])
        if parent:
            text = parent.get_text(" ", strip=True)
            if text:
                return text
        return anchor.get_text(" ", strip=True) or None

    def _is_internal_url(self, url: str) -> bool:
        parsed = urlparse(url)
        base = urlparse(self.base_url)
        return parsed.netloc == base.netloc or (not parsed.netloc and parsed.path)

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        path = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        fragment = ""
        return f"{scheme}://{netloc}{path}{query}{fragment}" if netloc else url

    @staticmethod
    def _extract_page_title(soup: BeautifulSoup) -> Optional[str]:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    # ------------------------------------------------------------------
    def to_dataframe(self, resources: Iterable[ResourceRecord]):
        try:
            import pandas as pd  # type: ignore
        except ImportError as exc:  # pragma: no cover - pandas optional at runtime
            raise RuntimeError(
                "pandas is required to export resources to a dataframe"
            ) from exc

        data = [resource.as_dict() for resource in resources]
        return pd.DataFrame(data)


__all__ = ["BFSkinnerScraper", "ResourceRecord"]
