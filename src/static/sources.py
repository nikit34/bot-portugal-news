import os

telegram_debug_chat_id = '-1002178707665'
self_facebook_page_id = '348454375016310'
self_instagram_channel = '17841467413345329'

telegram_channels = {
    1646641886: "https://t.me/sportingcp_oficial",
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
storage = os.getcwd() + '/db.sqlite3'

platforms = {
    'facebook': True,
    'instagram': False,
}
