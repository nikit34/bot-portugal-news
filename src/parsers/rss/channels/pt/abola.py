import logging

import httpx
from bs4 import BeautifulSoup

from src.parsers.rss.user_agents_manager import random_user_agent_headers
from src.static.settings import HTTP_REQUEST_TIMEOUT

logger = logging.getLogger('app')


def is_valid_abola_entry(entry):
    has_title = bool(entry.get('title'))
    has_link = bool(entry.get('link'))

    logger.debug(f"Abola entry check - has_title: {has_title}, has_link: {has_link}")
    return has_title and has_link


def _extract_og(soup, prop):
    tag = soup.find('meta', attrs={'property': prop})
    content = tag.get('content') if tag else None
    return content.strip() if content else ''


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
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=HTTP_REQUEST_TIMEOUT) as client:
                response = await client.get(article_url, headers=random_user_agent_headers())
                response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            image = _extract_og(soup, 'og:image')
            summary = _extract_og(soup, 'og:description')
            logger.debug(f"Found Abola image URL: {image}")
        except Exception:
            logger.warning(f"[RSS] Failed to fetch Abola article: {article_url}", exc_info=True)

    message = title + ('\n' if title and summary else '') + summary

    if not image or not message:
        logger.error("No image or message found in Abola entry")

    return message, image
