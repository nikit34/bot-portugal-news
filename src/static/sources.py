import os

self_telegram_channel = 'https://t.me/sportportugal'

telegram_channels = {
    # 2178707665: 'https://t.me/+M-LLGrMDui1hZjhi'  # For debug
}

rss_channels = {
    'abola.pt': 'https://www.abola.pt/api/rss',
    'abola.pt/nacional': 'https://www.abola.pt/rss/nacional',
    'abola.pt/internacional': 'https://www.abola.pt/rss/internacional',
    'abola.pt/modalidades': 'https://www.abola.pt/rss/modalidades',
    'abola.pt/motores': 'https://www.abola.pt/rss/motores',
    'bbc.com/football': 'https://feeds.bbci.co.uk/sport/football/rss.xml'
}

tmp_folder = os.getcwd() + '/tmp'

translations = {
    '🇷🇺': 'ru',
    '🇬🇧': 'en'
}
