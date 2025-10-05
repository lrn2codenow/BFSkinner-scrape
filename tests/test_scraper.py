import pytest
from unittest import mock
import urllib.error

from bfskinner_scrape import ArticleRecord, Scraper, ScraperError


def make_http_response(html: str, *, charset: str = "utf-8"):
    response = mock.Mock()
    response.read.return_value = html.encode(charset)
    response.headers = mock.Mock()
    response.headers.get_content_charset.return_value = charset
    response.__enter__ = mock.Mock(return_value=response)
    response.__exit__ = mock.Mock(return_value=None)
    return response


def test_parse_listing_extracts_articles_and_next_link():
    html = """
    <html>
        <body>
            <section id="posts">
                <article>
                    <h2 class="entry-title"><a href="/article-1">The first article</a></h2>
                    <time datetime="2020-01-01">January 1, 2020</time>
                    <p class="excerpt">A short summary of the first piece.</p>
                </article>
                <article>
                    <h2 class="entry-title"><a href="https://example.com/article-2">Second article</a></h2>
                    <time datetime="2021-03-04">March 4, 2021</time>
                    <p>Follow-up research and commentary.</p>
                </article>
            </section>
            <nav class="pagination">
                <a class="next" href="/page/2">Next page</a>
            </nav>
        </body>
    </html>
    """
    scraper = Scraper("https://example.com")

    articles, next_link = scraper.parse_listing(html)

    assert articles == [
        ArticleRecord(
            title="The first article",
            url="https://example.com/article-1",
            summary="A short summary of the first piece.",
            published="2020-01-01",
        ),
        ArticleRecord(
            title="Second article",
            url="https://example.com/article-2",
            summary="Follow-up research and commentary.",
            published="2021-03-04",
        ),
    ]
    assert next_link == "https://example.com/page/2"


@pytest.mark.parametrize(
    "html",
    [
        "<html><body><article><h2>No link available</h2></article></body></html>",
        "<html><body><article><h2><a>Missing href</a></h2></article></body></html>",
    ],
)
def test_parse_listing_skips_incomplete_articles(html):
    scraper = Scraper("https://example.com")

    articles, next_link = scraper.parse_listing(html)

    assert articles == []
    assert next_link is None


def test_parse_listing_rejects_invalid_html():
    scraper = Scraper("https://example.com")

    with pytest.raises(ScraperError):
        scraper.parse_listing("<html><body><article>")


def test_fetch_success():
    opener = mock.Mock()
    opener.open.return_value = make_http_response("<html></html>")
    scraper = Scraper("https://example.com", opener=opener)

    assert scraper._fetch("https://example.com/feed") == "<html></html>"

    assert opener.open.call_count == 1
    request_arg, kwargs = opener.open.call_args
    assert request_arg[0].full_url == "https://example.com/feed"
    headers = dict(request_arg[0].header_items())
    assert headers.get("User-agent") == scraper.headers["User-Agent"]
    assert kwargs["timeout"] == scraper.timeout


def test_fetch_converts_url_errors():
    opener = mock.Mock()
    opener.open.side_effect = urllib.error.URLError("boom")
    scraper = Scraper("https://example.com", opener=opener)

    with pytest.raises(ScraperError):
        scraper._fetch("https://example.com/feed")


def test_fetch_wraps_http_error():
    opener = mock.Mock()
    opener.open.side_effect = urllib.error.HTTPError(
        url="https://example.com/feed", code=500, msg="fail", hdrs=None, fp=None
    )
    scraper = Scraper("https://example.com", opener=opener)

    with pytest.raises(ScraperError):
        scraper._fetch("https://example.com/feed")


def test_scrape_follows_pagination_and_deduplicates():
    first_page = """
    <html>
        <body>
            <article>
                <h2><a href="/one">One</a></h2>
                <time datetime="2020-01-01">January 1, 2020</time>
                <p>First page summary.</p>
            </article>
            <a rel="next" href="/page/2">More</a>
        </body>
    </html>
    """
    second_page = """
    <html>
        <body>
            <article>
                <h2><a href="/one">One</a></h2>
                <time datetime="2020-01-01">January 1, 2020</time>
                <p>Duplicate item that should be ignored.</p>
            </article>
            <article>
                <h2><a href="/two">Two</a></h2>
                <p>Brand new content.</p>
            </article>
        </body>
    </html>
    """

    opener = mock.Mock()
    opener.open.side_effect = [
        make_http_response(first_page),
        make_http_response(second_page),
    ]
    scraper = Scraper("https://example.com", opener=opener)

    records = scraper.scrape()

    assert records == [
        ArticleRecord(
            title="One",
            url="https://example.com/one",
            summary="First page summary.",
            published="2020-01-01",
        ),
        ArticleRecord(
            title="Two",
            url="https://example.com/two",
            summary="Brand new content.",
            published=None,
        ),
    ]
    assert [call.args[0].full_url for call in opener.open.call_args_list] == [
        "https://example.com",
        "https://example.com/page/2",
    ]
    assert all(call.kwargs["timeout"] == scraper.timeout for call in opener.open.call_args_list)


def test_scrape_stops_when_next_page_loops_back():
    first_page = """
    <html>
        <body>
            <article>
                <h2><a href="/loop">Loop</a></h2>
            </article>
            <a class="next" href="/page/2">Next</a>
        </body>
    </html>
    """
    second_page = """
    <html>
        <body>
            <article>
                <h2><a href="/second">Second</a></h2>
            </article>
            <a class="next" href="/">Back</a>
        </body>
    </html>
    """

    opener = mock.Mock()
    opener.open.side_effect = [
        make_http_response(first_page),
        make_http_response(second_page),
    ]
    scraper = Scraper("https://example.com/", opener=opener)

    records = scraper.scrape()

    assert [record.url for record in records] == [
        "https://example.com/loop",
        "https://example.com/second",
    ]
