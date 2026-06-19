import calendar
import time

import src.parsers.youtube.parser as yt
from src.parsers.youtube.parser import _too_old, _FEED_URL


def _struct_days_ago(days):
    return time.gmtime(time.time() - days * 86400)


def test_feed_url_uses_channel_id():
    url = _FEED_URL.format(channel_id="UC123")
    assert url == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"


def test_too_old_true_for_old_entry(monkeypatch):
    monkeypatch.setattr(yt, 'YOUTUBE_MAX_AGE_DAYS', 3)
    now = time.time()
    entry = {'published_parsed': _struct_days_ago(10)}
    assert _too_old(entry, now) is True


def test_too_old_false_for_fresh_entry(monkeypatch):
    monkeypatch.setattr(yt, 'YOUTUBE_MAX_AGE_DAYS', 3)
    now = time.time()
    entry = {'published_parsed': _struct_days_ago(1)}
    assert _too_old(entry, now) is False


def test_too_old_false_when_no_date():
    # нет даты публикации — по возрасту не отбраковываем
    assert _too_old({}, time.time()) is False
