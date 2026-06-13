import asyncio

import pytest

import src.parsers.rss.channels.pt.abola as abola
from src.parsers.rss.channels.pt.abola import is_valid_abola_entry, parse_abola_pt


@pytest.fixture(autouse=True)
def _fresh_semaphore():
    # pytest-asyncio uses a fresh event loop per test; recreate the module-level
    # semaphore so it binds to the current loop instead of a previous one, and reset
    # the lazily-cached shared httpx client so each test picks up its own patched one.
    abola._fetch_semaphore = asyncio.Semaphore(abola.ABOLA_FETCH_CONCURRENCY)
    abola._client = None
    yield


@pytest.mark.parametrize("entry,expected", [
    # Valid: has both title and article link
    ({'title': 'Test title', 'link': 'https://www.abola.pt/noticias/x'}, True),
    # Invalid: no link
    ({'title': 'Test title'}, False),
    # Invalid: no title
    ({'link': 'https://www.abola.pt/noticias/x'}, False),
    # Invalid: empty entry
    ({}, False),
])
def test_is_valid_abola_entry(entry, expected):
    assert is_valid_abola_entry(entry) == expected


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient."""

    def __init__(self, text=None, raise_on_get=False):
        self._text = text
        self._raise_on_get = raise_on_get
        self.get_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        self.get_calls += 1
        if self._raise_on_get:
            raise RuntimeError("boom")
        return _FakeResponse(self._text)


def _patch_client(mocker, client):
    return mocker.patch.object(abola.httpx, 'AsyncClient', return_value=client)


_ARTICLE_HTML = """
<html><head>
<meta property="og:image" content="https://img.example.com/pic.webp">
<meta property="og:description" content="Resumo do artigo">
</head><body></body></html>
"""


async def test_parse_abola_pt_full(mocker):
    _patch_client(mocker, _FakeClient(text=_ARTICLE_HTML))
    entry = {'title': 'Title', 'link': 'https://www.abola.pt/noticias/x'}

    message, image = await parse_abola_pt(entry)

    assert message == 'Title\nResumo do artigo'
    assert image == 'https://img.example.com/pic.webp'


async def test_parse_abola_pt_image_only(mocker):
    html = '<html><head><meta property="og:image" content="https://img.example.com/pic.webp"></head></html>'
    _patch_client(mocker, _FakeClient(text=html))
    entry = {'title': 'Title', 'link': 'https://www.abola.pt/noticias/x'}

    message, image = await parse_abola_pt(entry)

    assert message == 'Title'
    assert image == 'https://img.example.com/pic.webp'


async def test_parse_abola_pt_no_image(mocker):
    html = '<html><head><meta property="og:description" content="Resumo"></head></html>'
    _patch_client(mocker, _FakeClient(text=html))
    entry = {'title': 'Title', 'link': 'https://www.abola.pt/noticias/x'}

    message, image = await parse_abola_pt(entry)

    assert message == 'Title\nResumo'
    assert image == ''


async def test_parse_abola_pt_no_link_skips_fetch(mocker):
    client = _FakeClient(text=_ARTICLE_HTML)
    _patch_client(mocker, client)

    message, image = await parse_abola_pt({'title': 'Title'})

    assert message == 'Title'
    assert image == ''
    assert client.get_calls == 0


async def test_parse_abola_pt_fetch_failure_is_graceful(mocker):
    async def _instant_sleep(*args, **kwargs):
        return None
    mocker.patch.object(abola.asyncio, 'sleep', _instant_sleep)
    client = _FakeClient(raise_on_get=True)
    _patch_client(mocker, client)
    entry = {'title': 'Title', 'link': 'https://www.abola.pt/noticias/x'}

    message, image = await parse_abola_pt(entry)

    assert message == 'Title'
    assert image == ''
    # initial attempt + ABOLA_FETCH_RETRIES retries
    assert client.get_calls == abola.ABOLA_FETCH_RETRIES + 1
