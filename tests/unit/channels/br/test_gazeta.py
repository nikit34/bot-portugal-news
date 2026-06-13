import pytest
from src.parsers.rss.channels.br.gazeta import is_valid_gazeta_entry, parse_gazeta


@pytest.mark.parametrize("entry,expected", [
    # Valid - title and media:thumbnail
    ({
        'title': 'Test title',
        'summary': '<p>Some text</p>',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, True),

    # Invalid - no title
    ({
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, False),

    # Invalid - no thumbnail
    ({
        'title': 'Test title',
        'media_thumbnail': []
    }, False),

    # Invalid - thumbnail without url
    ({
        'title': 'Test title',
        'media_thumbnail': [{}]
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_gazeta_entry(entry, expected):
    assert is_valid_gazeta_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # WordPress "O post ... apareceu primeiro em ..." footer is dropped
    ({
        'title': 'Weah espera Paraguai agressivo',
        'summary': '<p>O atacante projeta o primeiro jogo.</p>\n'
                    '<p>O post <a href="http://x">Weah espera</a> apareceu primeiro em '
                    '<a href="http://x">Gazeta Esportiva</a>.</p>',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Weah espera Paraguai agressivo\nO atacante projeta o primeiro jogo.',
       'http://example.com/image.jpg'),

    # Plain summary without footer
    ({
        'title': 'Title',
        'summary': '<p>Body text</p>',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Title\nBody text', 'http://example.com/image.jpg'),

    # No thumbnail
    ({
        'title': 'Title',
        'summary': '<p>Body</p>',
        'media_thumbnail': []
    }, 'Title\nBody', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_gazeta(entry, expected_message, expected_image):
    message, image = parse_gazeta(entry)
    assert message == expected_message
    assert image == expected_image
