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

    # Valid - record.pt article under a sport section
    ({
        'title': 'Samu segue para o estágio do FC Porto',
        'link': 'https://www.record.pt/futebol/fc-porto/detalhe/samu-estagio',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, True),

    # Valid - internacional section
    ({
        'title': 'Messi após a vitória',
        'link': 'https://www.record.pt/internacional/detalhe/messi',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, True),

    # Invalid - general news under a non-sport section (the "médicos de família" leak)
    ({
        'title': 'Registo Nacional de Utentes muda atribuição de médicos de família',
        'link': 'https://www.record.pt/sociedade/detalhe/utentes',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, False),

    # Invalid - cross-network Cofina link (not record.pt)
    ({
        'title': 'Cross-promoted item',
        'link': 'https://www.cmjornal.pt/portugal/detalhe/x',
        'enclosures': [{'href': 'http://example.com/image.jpg'}]
    }, False),
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

    # The 220x220 thumbnail is upsized to the 800x533 variant so it clears the quality gate
    ({
        'title': 'Vizela estreia-se',
        'summary': '',
        'enclosures': [{'href': 'https://cdn.record.pt/images/2026-06/img_220x220uu2026-06-09.jpg'}]
    }, 'Vizela estreia-se', 'https://cdn.record.pt/images/2026-06/img_800x533uu2026-06-09.jpg'),

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
