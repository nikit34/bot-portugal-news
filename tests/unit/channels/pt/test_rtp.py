import pytest
from src.parsers.rss.channels.pt.rtp import is_valid_rtp_entry, parse_rtp_pt


@pytest.mark.parametrize("entry,expected", [
    # Valid - title and an inline <img> in the summary
    ({
        'title': 'Test title',
        'summary': '<img src="http://example.com/image.jpg" /> Some text'
    }, True),

    # Invalid - no title
    ({
        'summary': '<img src="http://example.com/image.jpg" />'
    }, False),

    # Invalid - no image in summary
    ({
        'title': 'Test title',
        'summary': 'Some text without an image'
    }, False),

    # Invalid - empty entry
    ({}, False),
])
def test_is_valid_rtp_entry(entry, expected):
    assert is_valid_rtp_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Image extracted from summary, tags stripped from the body
    ({
        'title': 'Pepa é o novo treinador',
        'summary': '<img src="http://example.com/image.jpg" /> Estrela da Amadora'
    }, 'Pepa é o novo treinador\nEstrela da Amadora', 'http://example.com/image.jpg'),

    # HTML-escaped query separators are unescaped AND the resizer w/q are bumped up
    # so RTP serves a full-size, higher-quality image instead of a ~350px thumbnail.
    ({
        'title': 'Title',
        'summary': '<img src="http://example.com/i?w=350&amp;q=50&amp;auto=format" /> Body'
    }, 'Title\nBody', 'http://example.com/i?w=1200&q=80&auto=format'),

    # Whitespace from stripped tags is collapsed
    ({
        'title': 'Title',
        'summary': '<img src="http://example.com/i.jpg" />   <p>A</p>\n<p>B</p>'
    }, 'Title\nA B', 'http://example.com/i.jpg'),

    # No image
    ({
        'title': 'Title',
        'summary': 'No image here'
    }, 'Title\nNo image here', ''),

    # Empty entry
    ({}, '', ''),
])
def test_parse_rtp_pt(entry, expected_message, expected_image):
    message, image = parse_rtp_pt(entry)
    assert message == expected_message
    assert image == expected_image
