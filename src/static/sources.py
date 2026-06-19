import os
import json
from enum import Enum, auto


class Platform(Enum):
    ALL = auto()
    TELEGRAM = auto()
    FACEBOOK = auto()
    INSTAGRAM = auto()


_REQUIRED_SELF_KEYS = ('telegram_channel', 'telegram_debug_chat_id', 'facebook_page_id', 'instagram_channel')
_REQUIRED_TOP_KEYS = ('platforms', 'self', 'telegram_channels', 'rss_channels')


def _load_config(config_name):
    config_path = os.path.join(os.path.dirname(__file__), 'configs', f'{config_name}.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config


def _validate_config(config_name, config):
    # Fail fast at startup with a clear message instead of a mid-run KeyError.
    missing_top = [k for k in _REQUIRED_TOP_KEYS if k not in config]
    if missing_top:
        raise ValueError(f"config '{config_name}': missing top-level keys: {missing_top}")
    missing_self = [k for k in _REQUIRED_SELF_KEYS if k not in config.get('self', {})]
    if missing_self:
        raise ValueError(f"config '{config_name}': missing self.{{{', '.join(missing_self)}}}")
    if not isinstance(config['platforms'], dict) or not config['platforms']:
        raise ValueError(f"config '{config_name}': 'platforms' must be a non-empty object")
    for platform in config['platforms']:
        if not hasattr(Platform, platform):
            raise ValueError(f"config '{config_name}': unknown platform '{platform}'")


def get_config(config_name):
    config = _load_config(config_name)
    _validate_config(config_name, config)

    platforms = {}
    for platform, value in config['platforms'].items():
        platforms[getattr(Platform, platform)] = value

    return {
        'platforms': platforms,
        'self_telegram_channel': config['self']['telegram_channel'],
        'self_telegram_debug_chat_id': config['self']['telegram_debug_chat_id'],
        'self_facebook_page_id': config['self']['facebook_page_id'],
        'self_instagram_channel': config['self']['instagram_channel'],
        'telegram_channels': config['telegram_channels'],
        'rss_channels': config['rss_channels'],
        # Необязательный: map "имя источника" -> YouTube channel_id (UC...). Источник
        # видео, включается флагом YOUTUBE_ENABLED. Старые конфиги без ключа работают.
        'youtube_channels': config.get('youtube_channels', {}),
    }

tmp_folder = os.getcwd() + '/tmp'

