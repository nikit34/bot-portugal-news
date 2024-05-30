import re
from PIL import Image
import requests
from io import BytesIO


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
    pattern = re.compile(r"/\d+/cpsprodpb")
    resize_image = re.sub(pattern, f'/960/cpsprodpb', image)
    if resize_image[-4:] == '.png':
        response = requests.get(resize_image)
        im = Image.open(BytesIO(response.content))
        im.save('tmp/image.jpg')
        resize_image = 'tmp/image.jpg'
    return message, link, resize_image
