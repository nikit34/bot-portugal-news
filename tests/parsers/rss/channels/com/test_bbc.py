import pytest
from src.parsers.rss.channels.com.bbc import is_valid_bbc_com_entry, parse_bbc_com


@pytest.mark.parametrize("entry,expected", [
    # Valid case with both text and media
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, True),
    
    # Valid case with only title and media
    ({
        'title': 'Test title',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, True),
    
    # Valid case with only summary and media
    ({
        'summary': 'Test summary',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, True),
    
    # Invalid case - no text
    ({
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, False),
    
    # Invalid case - no media
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': []
    }, False),
    
    # Invalid case - media without url
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': [{}]
    }, False),
    
    # Invalid case - empty media_thumbnail
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': None
    }, False),
    
    # Invalid case - empty entry
    ({}, False),
])
def test_is_valid_bbc_com_entry(entry, expected):
    assert is_valid_bbc_com_entry(entry) == expected


@pytest.mark.parametrize("entry,expected_message,expected_image", [
    # Full valid case
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title\nTest summary', 'http://example.com/image.jpg'),
    
    # Only title and media
    ({
        'title': 'Test title',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test title', 'http://example.com/image.jpg'),
    
    # Only summary and media
    ({
        'summary': 'Test summary',
        'media_thumbnail': [{'url': 'http://example.com/image.jpg'}]
    }, 'Test summary', 'http://example.com/image.jpg'),
    
    # Image with cpsprodpb parameter
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': [{'url': 'http://example.com/100/cpsprodpb/image.jpg'}]
    }, 'Test title\nTest summary', 'http://example.com/960/cpsprodpb/image.jpg'),
    
    # Multiple media thumbnails
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': [
            {'url': 'http://example.com/image1.jpg'},
            {'url': 'http://example.com/image2.jpg'}
        ]
    }, 'Test title\nTest summary', 'http://example.com/image1.jpg'),
    
    # No media
    ({
        'summary': 'Test summary',
        'title': 'Test title',
        'media_thumbnail': []
    }, 'Test title\nTest summary', ''),
    
    # Empty entry
    ({}, '', ''),
])
def test_parse_bbc_com(entry, expected_message, expected_image):
    message, image = parse_bbc_com(entry)
    assert message == expected_message
    assert image == expected_image 