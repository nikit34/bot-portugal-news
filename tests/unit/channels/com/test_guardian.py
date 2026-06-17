import pytest
from src.parsers.rss.channels.com.guardian import is_valid_guardian_entry, parse_guardian


@pytest.mark.parametrize("entry,expected", [
    # Valid: title + a media:content variant
    ({
        'title': 'Test title',
        'media_content': [{'url': 'http://example.com/700.jpg', 'width': '700'}],
    }, True),

    # Valid: title + summary + media
    ({
        'title': 'Test title',
        'summary': '<p>Some summary</p>',
        'media_content': [{'url': 'http://example.com/460.jpg', 'width': '460'}],
    }, True),

    # Invalid: no title (Guardian always has one; summary alone is not enough)
    ({
        'summary': '<p>Some summary</p>',
        'media_content': [{'url': 'http://example.com/700.jpg', 'width': '700'}],
    }, False),

    # Invalid: no media
    ({
        'title': 'Test title',
        'media_content': [],
    }, False),

    # Invalid: media item without url
    ({
        'title': 'Test title',
        'media_content': [{'width': '700'}],
    }, False),

    # Invalid: media_content missing entirely
    ({
        'title': 'Test title',
    }, False),

    # Invalid: empty entry
    ({}, False),
])
def test_is_valid_guardian_entry(entry, expected):
    assert is_valid_guardian_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Picks the widest variant and keeps its signed URL verbatim
    ({
        'title': 'Test title',
        'summary': '<p>Hello <a href="x">world</a></p>',
        'media_content': [
            {'url': 'http://example.com/140.jpg?s=a', 'width': '140'},
            {'url': 'http://example.com/700.jpg?s=c', 'width': '700'},
            {'url': 'http://example.com/460.jpg?s=b', 'width': '460'},
        ],
    }, 'Test title\nHello world', 'http://example.com/700.jpg?s=c'),

    # Title only (no summary) -> message is just the title
    ({
        'title': 'Test title',
        'media_content': [{'url': 'http://example.com/700.jpg', 'width': '700'}],
    }, 'Test title', 'http://example.com/700.jpg'),

    # HTML entities in the summary are unescaped and tags stripped
    ({
        'title': 'Title',
        'summary': '<p>Caf&eacute; &amp; bola</p>',
        'media_content': [{'url': 'http://example.com/700.jpg', 'width': '700'}],
    }, 'Title\nCafé & bola', 'http://example.com/700.jpg'),

    # Missing/garbage width falls back gracefully (still returns a url)
    ({
        'title': 'Title',
        'media_content': [{'url': 'http://example.com/only.jpg'}],
    }, 'Title', 'http://example.com/only.jpg'),

    # No media -> empty image
    ({
        'title': 'Title',
        'media_content': [],
    }, 'Title', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_guardian(entry, expected_message, expected_image):
    message, image = parse_guardian(entry)
    assert message == expected_message
    assert image == expected_image
