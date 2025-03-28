import pytest
from unittest.mock import Mock, patch, AsyncMock
import facebook as fb

from src.processor.service import serve
from src.static.settings import TARGET_LANGUAGE

@pytest.mark.asyncio
async def test_serve_integration(posted_q, test_image_path):
    graph = Mock(spec=fb.GraphAPI)
    nlp = Mock()
    translator = Mock()
    translator.translate.return_value = Mock(text="Переведенный текст")
    
    message_text = "Test message"
    
    mock_handler = AsyncMock()
    mock_handler.return_value = {
        'url': 'https://example.com/image.jpg',
        'path': test_image_path
    }
    
    with patch('src.processor.service._low_semantic_load', return_value=False), \
         patch('src.processor.service.facebook_prepare_post') as mock_fb_prepare, \
         patch('src.processor.service.facebook_send_message', new_callable=AsyncMock) as mock_fb_send:
        
        mock_fb_prepare.return_value = "Подготовленный пост"
        
        await serve(graph, nlp, translator, message_text, mock_handler, posted_q)
        
        translator.translate.assert_called_once_with(message_text, dest=TARGET_LANGUAGE)
        mock_fb_prepare.assert_called_once()
        mock_fb_send.assert_called_once()
        assert len(posted_q) == 1

@pytest.mark.asyncio
async def test_serve_integration_with_duplicate():
    graph = Mock(spec=fb.GraphAPI)
    nlp = Mock()
    translator = Mock()
    translator.translate.return_value = Mock(text="Duplicate text")
    
    message_text = "Test message"
    posted_q = ["Duplicate text"]
    
    mock_handler = Mock()
    
    with patch('src.processor.service._low_semantic_load', return_value=False), \
         patch('src.processor.service.facebook_prepare_post') as mock_fb_prepare, \
         patch('src.processor.service.facebook_send_message') as mock_fb_send:
        
        await serve(graph, nlp, translator, message_text, mock_handler, posted_q)
        
        translator.translate.assert_called_once()
        mock_fb_prepare.assert_not_called()
        mock_fb_send.assert_not_called() 