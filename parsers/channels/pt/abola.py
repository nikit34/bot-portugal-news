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
    return message, link, image
