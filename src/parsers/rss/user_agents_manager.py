from random import randint
from src.static.user_agents import user_agents


def random_user_agent_headers():
    rnd_index = randint(0, len(user_agents) - 1)
    return {
        'User-Agent': user_agents[rnd_index],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        # No 'br': httpx has no brotli decoder here, so advertising it makes servers
        # return undecodable bodies (garbled text, missing tags). gzip/deflate are native.
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
    }