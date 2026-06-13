import re
import logging

logger = logging.getLogger('app')


def _thumbnail(entry):
    media_thumbnail = entry.get('media_thumbnail', [])
    return media_thumbnail[0].get('url', '') if media_thumbnail else ''


def is_valid_gazeta_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(_thumbnail(entry))

    logger.debug(f"Gazeta entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_gazeta(entry):
    logger.debug("Parsing Gazeta entry")
    title = entry.get('title', '')
    raw_summary = entry.get('summary', '')
    # WordPress appends a "O post <title> apareceu primeiro em <site>." footer paragraph
    # to every item; drop it so it does not leak into the post body.
    raw_summary = re.sub(r'<p>\s*O post\b.*', '', raw_summary, flags=re.DOTALL)
    summary = ' '.join(re.sub(r'<[^>]+>', '', raw_summary).split())

    message = title + ('\n' if title and summary else '') + summary
    image = _thumbnail(entry)
    logger.debug(f"Found Gazeta image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Gazeta entry")

    return message, image
