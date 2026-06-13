import re
import html
import logging

logger = logging.getLogger('app')


def _first_img(summary_html):
    # RTP carries no media tags; the article image is embedded in the description HTML,
    # where the URL keeps HTML-escaped query separators (&amp;) that break the download.
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    return _upscale(html.unescape(match.group(1))) if match else ''


def _upscale(url):
    # RTP serves images through a resizer CDN (cdn-images.rtp.pt) that bakes a small
    # w=350&q=50 into the feed URL — ~350px, looks bad in the feed. The CDN honours a
    # larger w/q, so request a full-size, higher-quality render from the same source.
    url = re.sub(r'([?&]w=)\d+', r'\g<1>1200', url)
    url = re.sub(r'([?&]q=)\d+', r'\g<1>80', url)
    return url


def is_valid_rtp_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(_first_img(entry.get('summary', '')))

    logger.debug(f"RTP entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_rtp_pt(entry):
    logger.debug("Parsing RTP entry")
    title = entry.get('title', '')
    raw_summary = entry.get('summary', '')

    image = _first_img(raw_summary)
    summary = ' '.join(re.sub(r'<[^>]+>', '', raw_summary).split())

    message = title + ('\n' if title and summary else '') + summary
    logger.debug(f"Found RTP image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in RTP entry")

    return message, image
