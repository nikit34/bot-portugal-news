from io import BytesIO

import requests
from PIL import Image


def change_format_image(url_image):
    response = requests.get(url_image)
    im = Image.open(BytesIO(response.content))
    im.save('tmp/image.jpg')
    return 'tmp/image.jpg'
