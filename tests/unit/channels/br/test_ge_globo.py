import pytest
from src.parsers.rss.channels.br.ge_globo import is_valid_ge_globo_entry, parse_ge_globo


@pytest.mark.parametrize("entry,expected", [
    # Valid - title and media:content
    ({
        'title': 'Test title',
        'summary': 'Some text',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),

    # Valid - title and inline <img> fallback (no media:content)
    ({
        'title': 'Test title',
        'summary': '<img src="http://example.com/image.jpg" /> Some text'
    }, True),

    # Invalid - live "Ao vivo" page: no media and no inline image
    ({
        'title': 'Estados Unidos x Paraguai - Ao vivo',
        'summary': 'acompanhe tudo sobre o jogo'
    }, False),

    # Invalid - no title
    ({
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_ge_globo_entry(entry, expected):
    assert is_valid_ge_globo_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # media:content preferred
    ({
        'title': 'Brasileiros vão à loucura',
        'summary': 'A espera acabou',
        'media_content': [{'url': 'http://example.com/media.jpg'}]
    }, 'Brasileiros vão à loucura\nA espera acabou', 'http://example.com/media.jpg'),

    # Falls back to inline <img>, body tags stripped
    ({
        'title': 'Cadáver é encontrado',
        'summary': '<img src="http://example.com/inline.jpg" /> Um cadáver foi encontrado'
    }, 'Cadáver é encontrado\nUm cadáver foi encontrado', 'http://example.com/inline.jpg'),

    # No image
    ({
        'title': 'Title',
        'summary': 'No image'
    }, 'Title\nNo image', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_ge_globo(entry, expected_message, expected_image):
    message, image = parse_ge_globo(entry)
    assert message == expected_message
    assert image == expected_image
