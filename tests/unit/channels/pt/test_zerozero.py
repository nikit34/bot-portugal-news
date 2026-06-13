import pytest
from src.parsers.rss.channels.pt.zerozero import is_valid_zerozero_entry, parse_zerozero_pt


@pytest.mark.parametrize("entry,expected", [
    # Valid - title and media (Zerozero items carry an empty summary)
    ({
        'title': 'Test title',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),

    # Invalid - no title
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

    # Invalid - media_content None
    ({
        'title': 'Test title',
        'media_content': None
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_zerozero_entry(entry, expected):
    assert is_valid_zerozero_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Title only (typical Zerozero item)
    ({
        'title': 'Test title',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title', 'http://example.com/image.jpg'),

    # Title and summary
    ({
        'title': 'Test title',
        'summary': 'Test summary',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),

    # Summary with HTML tags is stripped
    ({
        'title': 'Test title',
        'summary': '<p>Test <b>summary</b></p>',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),

    # No media
    ({
        'title': 'Test title',
        'media_content': []
    }, 'Test title', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_zerozero_pt(entry, expected_message, expected_image):
    message, image = parse_zerozero_pt(entry)
    assert message == expected_message
    assert image == expected_image
