import re

from src.parsers.channels.formatter import change_format_image


def check_sport_ru(entry):
    required_keys = ('summary', 'title', 'media_content', 'link')
    return not all(entry.get(key) for key in required_keys)


def parse_sport_ru(entry):
    summary = entry.get('summary')
    title = entry.get('title')
    message = title + '\n' + summary
    cleaned_message = re.sub(r'<.*?>', '', message)

    link = entry.get('link')
    image = entry.get('media_content')[0].get('url')
    image = change_format_image(image)
    return cleaned_message, link, image
