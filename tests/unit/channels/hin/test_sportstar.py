import pytest
from src.parsers.rss.channels.hin.sportstar import is_valid_sportstar_entry, parse_sportstar_entry


@pytest.mark.parametrize("entry,expected", [
    # Valid case with both text and media
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),
    
    # Valid case with only title and media
    ({
        'title': 'Test title',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),
    
    # Valid case with only description and media
    ({
        'description': 'Test description',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, True),
    
    # Invalid case - no text
    ({
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, False),
    
    # Invalid case - no media
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': []
    }, False),
    
    # Invalid case - media without url
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': [{}]
    }, False),
    
    # Invalid case - empty media_content
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': None
    }, False),
    
    # Invalid case - empty entry
    ({}, False),
])
def test_is_valid_sportstar_entry(entry, expected):
    assert is_valid_sportstar_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Full valid case
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest description', 'http://example.com/image.jpg'),
    
    # Only title and media
    ({
        'title': 'Test title',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title', 'http://example.com/image.jpg'),
    
    # Only description and media
    ({
        'description': 'Test description',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test description', 'http://example.com/image.jpg'),
    
    # Description with HTML tags
    ({
        'title': 'Test title',
        'description': '<p>Test <b>description</b></p>',
        'media_content': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest description', 'http://example.com/image.jpg'),
    
    # Multiple media content
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': [
            {'url': 'http://example.com/image1.jpg'},
            {'url': 'http://example.com/image2.jpg'}
        ]
    }, 'Test title\nTest description', 'http://example.com/image1.jpg'),
    
    # No media
    ({
        'title': 'Test title',
        'description': 'Test description',
        'media_content': []
    }, 'Test title\nTest description', ''),
    
    # Empty entry
    ({}, '', ''),
])
def test_parse_sportstar_entry(entry, expected_message, expected_image):
    message, image = parse_sportstar_entry(entry)
    assert message == expected_message
    assert image == expected_image 