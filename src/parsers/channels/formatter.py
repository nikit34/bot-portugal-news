from io import BytesIO

import requests
from PIL import Image


def change_format_image(url_image):
    response = requests.get(url_image)
    image = Image.open(BytesIO(response.content))
    rgb_image = image.convert('RGB')

    image_io = BytesIO()
    rgb_image.save(image_io, format='JPEG')
    image_io.seek(0)

    return image_io
