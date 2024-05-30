import re


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
    pattern = re.compile(r"standard/\d+/cpsprodpb")
    resize_image = re.sub(pattern, f'standard/960/cpsprodpb', image)
    return message, link, resize_image
