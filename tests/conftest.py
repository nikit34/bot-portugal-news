import os
import pytest
from collections import deque
import spacy
from googletrans import Translator
import facebook as fb

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
def test_image_path():
    return os.path.join(os.path.dirname(__file__), 'resources', 'test_image.jpg')