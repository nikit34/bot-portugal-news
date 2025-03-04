import os
import pytest
from collections import deque
from PIL import Image

from src.static.settings import COUNT_UNIQUE_MESSAGES

@pytest.fixture
def posted_q():
    return deque(maxlen=COUNT_UNIQUE_MESSAGES)

@pytest.fixture
def test_image_path(tmp_path):
    image_path = os.path.join(tmp_path, 'test_image.jpg')
    img = Image.new('RGB', (100, 100), color='red')
    img.save(image_path)
    return image_path
