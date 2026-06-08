import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

from src.parsers.rss.user_agents_manager import random_user_agent_headers
from src.static.settings import (
    HTTP_REQUEST_TIMEOUT,
    ABOLA_FETCH_CONCURRENCY,
    ABOLA_FETCH_RETRIES,
    ABOLA_FETCH_RETRY_DELAY,
)

logger = logging.getLogger('app')

# abola.pt resets connections when hit with many simultaneous article fetches, so cap
# the number of in-flight requests across all entries of a single run.
_fetch_semaphore = asyncio.Semaphore(ABOLA_FETCH_CONCURRENCY)


def is_valid_abola_entry(entry):
    has_title = bool(entry.get('title'))
    has_link = bool(entry.get('link'))

    logger.debug(f"Abola entry check - has_title: {has_title}, has_link: {has_link}")
    return has_title and has_link


def _extract_og(soup, prop):
    tag = soup.find('meta', attrs={'property': prop})
    content = tag.get('content') if tag else None
    return content.strip() if content else ''


async def _fetch_article(article_url):
    last_error = None
    for attempt in range(ABOLA_FETCH_RETRIES + 1):
        try:
            async with _fetch_semaphore:
                async with httpx.AsyncClient(follow_redirects=True, timeout=HTTP_REQUEST_TIMEOUT) as client:
                    response = await client.get(article_url, headers=random_user_agent_headers())
                    response.raise_for_status()
                    return response.text
        except Exception as error:
            last_error = error
            if attempt < ABOLA_FETCH_RETRIES:
                await asyncio.sleep(ABOLA_FETCH_RETRY_DELAY)

    logger.warning(
        f"[RSS] Failed to fetch Abola article {article_url}: "
        f"{type(last_error).__name__}: {last_error}"
    )
    return None


async def parse_abola_pt(entry):
    logger.debug("Parsing Abola entry")
    title = entry.get('title', '')
    article_url = entry.get('link', '')

    summary = ''
    image = ''
    if article_url:
        # abola.pt dropped per-item media and descriptions from its RSS feed (it now
        # carries only title/link/pubDate). The article page still exposes Open Graph
        # tags, so fetch it to recover the image and the summary.
        html = await _fetch_article(article_url)
        if html is not None:
            soup = BeautifulSoup(html, 'html.parser')
            image = _extract_og(soup, 'og:image')
            summary = _extract_og(soup, 'og:description')
            logger.debug(f"Found Abola image URL: {image}")

    message = title + ('\n' if title and summary else '') + summary

    if not image or not message:
        logger.error("No image or message found in Abola entry")

    return message, image
