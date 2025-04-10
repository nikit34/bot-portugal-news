import pytest
from src.parsers.rss.channels.com.bbc import is_valid_bbc_com_entry


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