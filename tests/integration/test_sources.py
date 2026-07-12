import os
import json
import pytest
from src.static.sources import _load_config, get_config, Platform, _validate_config


_OK_SELF = {'telegram_channel': 'x', 'telegram_debug_chat_id': 'x',
            'facebook_page_id': 'x', 'instagram_channel': 'x'}


def _cfg(**overrides):
    cfg = {'platforms': {'FACEBOOK': True}, 'self': dict(_OK_SELF),
           'telegram_channels': [], 'rss_channels': {}}
    cfg.update(overrides)
    return cfg


def test_validate_config_ok():
    _validate_config('ok', _cfg())  # no raise


def test_validate_config_missing_top_key():
    bad = _cfg()
    del bad['platforms']
    with pytest.raises(ValueError):
        _validate_config('bad', bad)


def test_validate_config_missing_self_key():
    with pytest.raises(ValueError):
        _validate_config('bad', _cfg(self={'telegram_channel': 'x'}))


def test_validate_config_unknown_platform():
    with pytest.raises(ValueError):
        _validate_config('bad', _cfg(platforms={'NOPE': True}))


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        _load_config('non_existent_config')


def test_food_br_config_is_valid():
    # The shipped 2nd-channel config must load + validate structurally so it's drop-in
    # once the real Page/IG ids are filled in (Meta setup). Placeholders are expected.
    config = get_config('food_br')
    assert all(isinstance(k, Platform) for k in config['platforms'].keys())
    assert Platform.FACEBOOK in config['platforms']
    assert Platform.INSTAGRAM in config['platforms']
    for key in ('self_facebook_page_id', 'self_instagram_channel', 'self_telegram_channel'):
        assert config[key]                       # present (placeholder until Meta setup)
    assert isinstance(config['rss_channels'], dict)
    assert isinstance(config['telegram_channels'], list)


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