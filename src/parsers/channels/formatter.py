from io import BytesIO

import uuid
import requests
from PIL import Image


def change_format_image(url_image):
    response = requests.get(url_image)
    image = Image.open(BytesIO(response.content))
    rgb_image = image.convert('RGB')
    unique_id = str(uuid.uuid4())
    rgb_image.save('tmp/image-' + unique_id + '.jpg')
    return 'tmp/image' + unique_id + '.jpg'
