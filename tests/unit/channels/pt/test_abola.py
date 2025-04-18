import pytest
from src.parsers.rss.channels.pt.abola import is_valid_abola_entry, parse_abola_pt


@pytest.mark.parametrize("entry,expected", [
    # Valid case with both text and image
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, True),
    
    # Valid case with only title and image
    ({
        'title': 'Test title',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, True),
    
    # Valid case with only summary and image
    ({
        'summary': 'Test summary',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, True),
    
    # Invalid case - no text
    ({
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, False),
    
    # Invalid case - no image
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': []
    }, False),
    
    # Invalid case - image without href
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': [{'type': 'image'}]
    }, False),
    
    # Invalid case - empty entry
    ({}, False),
])
def test_is_valid_abola_entry(entry, expected):
    assert is_valid_abola_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Full valid case
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),
    
    # Only title and image
    ({
        'title': 'Test title',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, 'Test title', 'http://example.com/image.jpg'),
    
    # Only summary and image
    ({
        'summary': 'Test summary',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg'}]
    }, 'Test summary', 'http://example.com/image.jpg'),
    
    # Image with fit parameter
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': [{'type': 'image', 'href': 'http://example.com/image.jpg?fit(100:100)'}]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg?fit(960:640)'),
    
    # Multiple links, first is image
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': [
            {'type': 'image', 'href': 'http://example.com/image.jpg'},
            {'type': 'other', 'href': 'http://example.com/other'}
        ]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),
    
    # Multiple links, second is image
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': [
            {'type': 'other', 'href': 'http://example.com/other'},
            {'type': 'image', 'href': 'http://example.com/image.jpg'}
        ]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),
    
    # No image
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'links': []
    }, 'Test title\nTest summary', ''),
    
    # Empty entry
    ({}, '', ''),
])
def test_parse_abola_pt(entry, expected_message, expected_image):
    message, image = parse_abola_pt(entry)
    assert message == expected_message
    assert image == expected_image