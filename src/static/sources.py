import os
import json
from enum import Enum, auto


class Platform(Enum):
    ALL = auto()
    TELEGRAM = auto()
    FACEBOOK = auto()
    INSTAGRAM = auto()

def _load_config(config_name):
    config_path = os.path.join(os.path.dirname(__file__), 'configs', f'{config_name}.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def get_config(config_name):
    config = _load_config(config_name)
    
    platforms = {}
    for platform, value in config['platforms'].items():
        platforms[getattr(Platform, platform)] = value
    
    return {
        'platforms': platforms,
        'self_telegram_channel': config['self']['telegram_channel'],
        'telegram_chat_id': config['self']['telegram_chat_id'],
        'telegram_debug_chat_id': config['self']['telegram_debug_chat_id'],
        'self_facebook_page_id': config['self']['facebook_page_id'],
        'self_instagram_channel': config['self']['instagram_channel'],
        'telegram_channels': config['telegram_channels'],
        'rss_channels': config['rss_channels'],
    }

tmp_folder = os.getcwd() + '/tmp'

