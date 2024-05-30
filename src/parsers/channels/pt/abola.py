import re

from src.parsers.channels.formatter import change_format_image


def check_abola_pt(entry):
    required_keys = ('summary', 'title', 'links', 'link')
    if not all(entry.get(key) for key in required_keys):
        for link_item in entry.get('links'):
            if 'image' in link_item.get('type'):
                return True
    return False


def parse_abola_pt(entry):
    summary = entry.get('summary')
    title = entry.get('title')
    message = title + '\n' + summary

    link = entry.get('link')
    image = ''
    for link_item in entry.get('links'):
        if 'image' in link_item.get('type'):
            image = link_item.get('href')
            image = re.sub(r"fit\(\d+:\d+\)", "fit(960:640)", image)
            if '.jpeg' in image:
                image = change_format_image(image)
    return message, link, image
