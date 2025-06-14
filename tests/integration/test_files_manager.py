import pytest
import os
from src.files_manager import SaveFileUrl, clean_tmp_folder
from src.static.sources import tmp_folder
from unittest.mock import patch

class TestFilesManager:
    @pytest.mark.asyncio
    async def test_save_file_url_success(self, image_path):
        test_url = "https://example.com/test.jpg"
        saver = SaveFileUrl(test_url)
        
        with patch('requests.get') as mock_get:
            with open(image_path, 'rb') as f:
                mock_get.return_value.content = f.read()
                mock_get.return_value.raise_for_status = lambda: None
            
            result = await saver()
            
            assert result['url'] == test_url
            assert os.path.exists(result['path'])
            assert result['path'].startswith(tmp_folder)
            
            os.remove(result['path'])
            
    @pytest.mark.asyncio
    async def test_save_file_url_failure(self):
        test_url = "https://example.com/nonexistent.jpg"
        saver = SaveFileUrl(test_url)
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.raise_for_status.side_effect = Exception("HTTP Error")
            
            with pytest.raises(Exception):
                await saver()

    def test_clean_tmp_folder(self):
        test_file = os.path.join(tmp_folder, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
            
        clean_tmp_folder()
        
        assert not os.path.exists(test_file)
        assert os.path.exists(os.path.join(tmp_folder, '.gitkeep'))