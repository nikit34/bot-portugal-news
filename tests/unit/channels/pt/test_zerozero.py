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

    # Entity-link markup resolves to the plain label
    ({
        'title': 'Dinis Telehovschi renova contrato com o SL Benfica',
        'summary': '{PLAYER_LINK|820441|Dinis Telehovschi}, medio de 19 anos, renovou pelo {TEAM_LINK|4|Benfica}',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    },
     'Dinis Telehovschi renova contrato com o SL Benfica\n'
     'Dinis Telehovschi, medio de 19 anos, renovou pelo Benfica',
     'http://example.com/image.jpg'),

    # Competition links and HTML entities in the same summary
    ({
        'title': 'Aten&ccedil;&atilde;o, Benfica',
        'summary': 'Depois da derrota na {COMPETITION_LINK|28|Liga Europa},&nbsp;a primeira m&atilde;o ficou resolvida',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    },
     'Atenção, Benfica\nDepois da derrota na Liga Europa, a primeira mão ficou resolvida',
     'http://example.com/image.jpg'),
])
def test_parse_zerozero_pt(entry, expected_message, expected_image):
    message, image = parse_zerozero_pt(entry)
    assert message == expected_message
    assert image == expected_image
