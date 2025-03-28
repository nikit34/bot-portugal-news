import re


def check_abola_pt(entry):
    required_keys = ('summary', 'title', 'links')
    if not all(entry.get(key) for key in required_keys):
        for link_item in entry.get('links'):
            if 'image' in link_item.get('type') and link_item.get('href'):
                return True
    return False


def parse_abola_pt(entry):
    summary = entry.get('summary')
    title = entry.get('title')

    message = title + '\n' + summary
    image = ''
    links = entry.get('links', [])
    for link_item in links:
        if link_item and 'image' in link_item.get('type', ''):
            image = link_item.get('href', '')
            if image:
                image = re.sub(r"fit\(\d+:\d+\)", "fit(960:640)", image)
            break

    return message, image
