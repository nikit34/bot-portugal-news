import os
import pytest
from collections import deque
import spacy
from googletrans import Translator
import facebook as fb
from PIL import Image

from src.static.settings import COUNT_UNIQUE_MESSAGES

@pytest.fixture
def nlp():
    return spacy.load('pt_core_news_sm')

@pytest.fixture
def translator():
    return Translator(service_urls=['translate.googleapis.com'])

@pytest.fixture
def graph():
    return fb.GraphAPI(access_token='test_token')

@pytest.fixture
def posted_q():
    return deque(maxlen=COUNT_UNIQUE_MESSAGES)

@pytest.fixture
def test_image_path(tmp_path):
    image_path = os.path.join(tmp_path, 'test_image.jpg')
    img = Image.new('RGB', (100, 100), color='red')
    img.save(image_path)
    return image_path

@pytest.fixture(autouse=True)
def setup_tmp_folder():
    if not os.path.exists('tmp'):
        os.makedirs('tmp')
    if not os.path.exists('tmp/.gitkeep'):
        with open('tmp/.gitkeep', 'w') as f:
            f.write('')