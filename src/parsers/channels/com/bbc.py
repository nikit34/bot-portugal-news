import re

from src.parsers.channels.formatter import change_format_image


def check_bbc_com(entry):
    required_keys = ('summary', 'title', 'media_thumbnail', 'link')
    if not all(entry.get(key) for key in required_keys):
        if len(entry.get('media_thumbnail')) > 0:
            return True
    return False


def parse_bbc_com(entry):
    summary = entry.get('summary')
    title = entry.get('title')
    message = title + '\n' + summary

    link = entry.get('link')
    image = entry.get('media_thumbnail')[0].get('url')
    image = re.sub(r"/\d+/cpsprodpb", f'/960/cpsprodpb', image)
    if image[-4:] == '.png':
        image = change_format_image(image)
    return message, link, image
