import pytest
from src.parsers.rss.channels.pt.record import is_valid_record_entry, parse_record_pt


@pytest.mark.parametrize("entry,expected", [
    # Valid - text and enclosure image
    ({
        'title': 'Test title',
        'summary': 'Test summary',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, True),

    # Valid - only title and enclosure
    ({
        'title': 'Test title',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, True),

    # Invalid - no text
    ({
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, False),

    # Invalid - no enclosure
    ({
        'title': 'Test title',
        'enclosures': []
    }, False),

    # Invalid - enclosure without href
    ({
        'title': 'Test title',
        'enclosures': [{}]
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_record_entry(entry, expected):
    assert is_valid_record_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # CDATA wrapper is stripped from the title
    ({
        'title': '<![CDATA[ Roberto Martínez sobre a viagem ]]>',
        'summary': 'Selecionador nacional lembrou a importância',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, 'Roberto Martínez sobre a viagem\nSelecionador nacional lembrou a importância',
       'http://example.com/image.jpg'),

    # Plain title without CDATA
    ({
        'title': 'Test title',
        'summary': 'Test summary',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),

    # Title only, empty summary
    ({
        'title': '<![CDATA[ Eles andam aí... ]]>',
        'summary': '',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, 'Eles andam aí...', 'http://example.com/image.jpg'),

    # No enclosure
    ({
        'title': 'Test title',
        'enclosures': []
    }, 'Test title', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_record_pt(entry, expected_message, expected_image):
    message, image = parse_record_pt(entry)
    assert message == expected_message
    assert image == expected_image
