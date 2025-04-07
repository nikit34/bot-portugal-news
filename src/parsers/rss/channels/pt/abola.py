import re
import logging

logger = logging.getLogger(__name__)


def is_valid_abola_entry(entry):
    required_keys = ('summary', 'title', 'links')
    has_required = all(entry.get(key) for key in required_keys)
        
    links = entry.get('links', [])
    has_image = any(
        'image' in link_item.get('type', '') and link_item.get('href')
        for link_item in links
    )
    
    logger.debug(f"Abola entry check - has_required: {has_required}, has_image: {has_image}")
    return( has_required or has_image)


def parse_abola_pt(entry):
    logger.debug("Parsing Abola entry")
    summary = entry.get('summary')
    title = entry.get('title')

    message = title + '\n' + summary
    image = ''
    links = entry.get('links', [])
    
    for link_item in links:
        if link_item and 'image' in link_item.get('type', ''):
            image = link_item.get('href', '')
            if image:
                logger.debug(f"Found Abola image URL: {image}")
                image = re.sub(r"fit\(\d+:\d+\)", "fit(960:640)", image)
                logger.debug(f"Modified Abola image URL: {image}")
                break
        else:
            logger.debug(f"Skipping non-image link: {link_item.get('type', 'unknown type')}")

    if not image:
        logger.warning("No image found in Abola entry")

    return message, image
