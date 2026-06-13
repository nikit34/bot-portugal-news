import pytest
from src.parsers.rss.channels.br.uol import is_valid_uol_entry, parse_uol


@pytest.mark.parametrize("entry,expected", [
    # Valid - title and an inline <img> opening the summary
    ({
        'title': 'Test title',
        'summary': '<img align="left" src="http://example.com/image.jpg" /> Some text'
    }, True),

    # Invalid - no title
    ({
        'summary': '<img src="http://example.com/image.jpg" />'
    }, False),

    # Invalid - no image (e.g. "Por Emily Green" stub)
    ({
        'title': 'Test title',
        'summary': 'Por Emily Green'
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_uol_entry(entry, expected):
    assert is_valid_uol_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Image pulled from the inline <img>, tags stripped from the body
    ({
        'title': 'Fritz vira outra',
        'summary': '<img align="left" src="http://example.com/image.jpg" /> Stuttgart - Mais uma vez'
    }, 'Fritz vira outra\nStuttgart - Mais uma vez', 'http://example.com/image.jpg'),

    # No image
    ({
        'title': 'Title',
        'summary': 'Por Emily Green'
    }, 'Title\nPor Emily Green', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_uol(entry, expected_message, expected_image):
    message, image = parse_uol(entry)
    assert message == expected_message
    assert image == expected_image
