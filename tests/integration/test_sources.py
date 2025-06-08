import os
import json
import pytest
from src.static.sources import _load_config, get_config, Platform

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

def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        _load_config('non_existent_config')

def test_full_config_loading(config_file, monkeypatch):
    def mock_join(*args):
        return config_file
    monkeypatch.setattr(os.path, 'join', mock_join)
    
    config = get_config('football')
    
    assert isinstance(config, dict)
    assert 'platforms' in config
    assert 'self_telegram_channel' in config
    assert 'telegram_channels' in config
    assert 'rss_channels' in config
    
    assert isinstance(config['platforms'], dict)
    assert isinstance(config['telegram_channels'], list)
    assert isinstance(config['rss_channels'], dict)
    
    assert all(isinstance(k, Platform) for k in config['platforms'].keys())
    assert all(isinstance(v, (bool, type(None))) for v in config['platforms'].values()) 