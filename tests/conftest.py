import os
import pytest
from collections import deque
from PIL import Image
import json

from src.static.settings import COUNT_UNIQUE_MESSAGES
from src.static.sources import Platform

@pytest.fixture
def posted_d():
    return {
        Platform.ALL: deque(maxlen=COUNT_UNIQUE_MESSAGES),
        Platform.FACEBOOK: deque(maxlen=COUNT_UNIQUE_MESSAGES),
        Platform.TELEGRAM: deque(maxlen=COUNT_UNIQUE_MESSAGES),
    }

@pytest.fixture
def posted_q():
    return deque(maxlen=COUNT_UNIQUE_MESSAGES)

@pytest.fixture
def image_path(tmp_path):
    image_path = os.path.join(tmp_path, 'test_image.jpg')
    img = Image.new('RGB', (100, 100), color='red')
    img.save(image_path)
    return image_path


@pytest.fixture
def config_file(tmp_path):
    config_data = {
        "platforms": {
            "ALL": None,
            "TELEGRAM": True,
            "FACEBOOK": True,
            "INSTAGRAM": True
        },
        "self": {
            "telegram_channel": "test_channel",
            "telegram_chat_id": "test_chat_id",
            "telegram_debug_chat_id": "test_debug_chat_id",
            "facebook_page_id": "test_facebook_id",
            "instagram_channel": "test_instagram_id"
        },
        "telegram_channels": ["channel1", "channel2"],
        "rss_channels": {"rss1": "url1", "rss2": "url2"}
    }

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "test.json"

    with open(config_file, 'w') as f:
        json.dump(config_data, f)

    return str(config_file)
