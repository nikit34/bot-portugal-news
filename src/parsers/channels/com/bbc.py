import re


def check_bbc_com(entry):
    required_keys = ('summary', 'title', 'media_thumbnail', 'link')
    return not (all(entry.get(key) for key in required_keys) or entry.get('media_thumbnail')[0].get('url'))


def parse_bbc_com(entry):
    summary = entry.get('summary')
    title = entry.get('title')

    message = title + '\n' + summary
    link = entry.get('link')
    image = entry.get('media_thumbnail')[0].get('url')
    image = re.sub(r"/\d+/cpsprodpb", f'/960/cpsprodpb', image)

    return message, link, image
