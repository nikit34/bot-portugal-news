from src.parsers.rss.user_agents_manager import random_user_agent_headers
from src.static.user_agents import user_agents


def test_random_user_agent_headers():
    headers = random_user_agent_headers()
    
    assert isinstance(headers, dict)
    assert 'User-Agent' in headers
    assert headers['User-Agent'] in user_agents
    assert headers['Accept'] == 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    assert headers['Accept-Language'] == 'en-US,en;q=0.5'
    assert headers['DNT'] == '1'


def test_random_user_agent_headers_multiple_calls():
    headers_set = {random_user_agent_headers()['User-Agent'] for _ in range(50)}
    assert len(headers_set) > 1 