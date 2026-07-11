import pytest
from src.parsers.rss.channels.br.metropoles import is_valid_metropoles_entry, parse_metropoles


@pytest.mark.parametrize("entry,expected", [
    # Valid - title and media:thumbnail
    ({
        'title': 'Test title',
        'summary': 'Some text',
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
def test_is_valid_metropoles_entry(entry, expected):
    assert is_valid_metropoles_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Plain-text summary (the common Metrópoles shape)
    ({
        'title': 'Com Haaland, Kane e Messi, dois duelos encerram as quartas',
        'summary': 'A partida tem transmissao ao vivo no canal do Metropoles',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Com Haaland, Kane e Messi, dois duelos encerram as quartas\n'
       'A partida tem transmissao ao vivo no canal do Metropoles',
       'http://example.com/image.jpg'),

    # WordPress "O post ... apareceu primeiro em ..." footer is dropped
    ({
        'title': 'Flamengo mira 18a vitoria',
        'summary': '<p>O tecnico projeta o duelo.</p>\n'
                   '<p>O post <a href="http://x">Flamengo mira</a> apareceu primeiro em '
                   '<a href="http://x">Metropoles</a>.</p>',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Flamengo mira 18a vitoria\nO tecnico projeta o duelo.',
       'http://example.com/image.jpg'),

    # No thumbnail
    ({
        'title': 'Title',
        'summary': 'Body',
        'media_thumbnail': []
    }, 'Title\nBody', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_metropoles(entry, expected_message, expected_image):
    message, image = parse_metropoles(entry)
    assert message == expected_message
    assert image == expected_image
