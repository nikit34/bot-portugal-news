import os

telegram_debug_chat_id = '-1002178707665'
self_facebook_page_id = '348454375016310'
self_instagram_channel = '17841467413345329'

telegram_channels = [
    # 'https://t.me/+M-LLGrMDui1hZjhi'  # For debug

    # "https://t.me/euro_football_ru",
    # 'https://t.me/MemesFutebol',
    'https://t.me/AO_VIVO_Futebol',
    'https://t.me/FutebolDaZoeira',
    'https://t.me/futebol_portugues',
    'https://t.me/Futebol_Brasileirao',
]

rss_channels = {
    'abola.pt': 'https://www.abola.pt/api/rss',
    'abola.pt/nacional': 'https://www.abola.pt/rss/nacional',
    'abola.pt/internacional': 'https://www.abola.pt/rss/internacional',
    # 'abola.pt/modalidades': 'https://www.abola.pt/rss/modalidades',
    # 'abola.pt/motores': 'https://www.abola.pt/rss/motores',
    'bbc.com/football': 'https://feeds.bbci.co.uk/sport/football/rss.xml',
    'sportstar.thehindu.com/football': 'https://sportstar.thehindu.com/football/feeder/default.rss',
    'sportstar.thehindu.com/football-highlights': 'https://sportstar.thehindu.com/football-highlights/feeder/default.rss',
    'sportstar.thehindu.com/football-videos': 'https://sportstar.thehindu.com/football-videos/feeder/default.rss',
}

tmp_folder = os.getcwd() + '/tmp'

platforms = {
    'facebook': True,
    'instagram': False,
}
