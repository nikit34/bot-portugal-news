import re
import logging

logger = logging.getLogger('app')


def is_valid_abola_entry(entry):
    required_keys = ('summary', 'title')
    has_text = any(entry.get(key) for key in required_keys)
        
    links = entry.get('links', [])
    has_media = any(
        'image' in link_item.get('type', '') and link_item.get('href')
        for link_item in links
    )
    
    logger.debug(f"Abola entry check - has_text: {has_text}, has_media: {has_media}")
    return (has_text and has_media)


def parse_abola_pt(entry):
    logger.debug("Parsing Abola entry")
    summary = entry.get('summary', '')
    title = entry.get('title', '')

    message = title + ('\n' if title and summary else '') + summary
    image = ''
    links = entry.get('links', [])
    
    for link_item in links:
        if link_item.get('href') and 'image' in link_item.get('type'):
            image = link_item.get('href')
            logger.debug(f"Found Abola image URL: {image}")
            image = re.sub(r"fit\(\d+:\d+\)", "fit(960:640)", image)
            logger.debug(f"Modified Abola image URL: {image}")
            break

    if not image or not message:
        logger.error("No image or message found in Abola entry")

    return message, image
