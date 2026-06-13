import pytest
from src.parsers.rss.channels.br.trivela import is_valid_trivela_entry, parse_trivela


@pytest.mark.parametrize("entry,expected", [
    # Valid - text and media:content
    ({
        'title': 'Test title',
        'summary': 'Test summary',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),

    # Valid - only summary and media
    ({
        'summary': 'Test summary',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),

    # Invalid - no text
    ({
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, False),

    # Invalid - no media
    ({
        'title': 'Test title',
        'media_content': []
    }, False),

    # Invalid - media without url
    ({
        'title': 'Test title',
        'media_content': [{}]
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_trivela_entry(entry, expected):
    assert is_valid_trivela_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Full case
    ({
        'title': 'Jogos exclusivos na Copa',
        'summary': 'A CazéTV é a grande novidade',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Jogos exclusivos na Copa\nA CazéTV é a grande novidade', 'http://example.com/image.jpg'),

    # Summary HTML stripped and whitespace collapsed
    ({
        'title': 'Title',
        'summary': '<p>A</p>\n<p>B</p>',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Title\nA B', 'http://example.com/image.jpg'),

    # No media
    ({
        'title': 'Title',
        'summary': 'Summary',
        'media_content': []
    }, 'Title\nSummary', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_trivela(entry, expected_message, expected_image):
    message, image = parse_trivela(entry)
    assert message == expected_message
    assert image == expected_image
