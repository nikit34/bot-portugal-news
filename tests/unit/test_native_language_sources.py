import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.static.sources import get_config, Platform


def _write_config(tmp_dir, name, payload):
    path = os.path.join(tmp_dir, f'{name}.json')
    with open(path, 'w') as handle:
        json.dump(payload, handle)
    return path


BASE = {
    'platforms': {'FACEBOOK': True},
    'self': {
        'telegram_channel': 'https://t.me/x',
        'telegram_debug_chat_id': '-1',
        'facebook_page_id': '1',
        'instagram_channel': '2',
    },
    'telegram_channels': [],
    'rss_channels': {},
}


def test_football_config_marks_the_portuguese_sources_as_native():
    context = get_config('football')
    assert 'zerozero.pt' in context['native_language_sources']
    assert 'abola.pt' in context['native_language_sources']
    assert 'https://t.me/futebol_portugues' in context['native_language_sources']
    # English-language feeds still need translating.
    assert 'bbc.com/football' not in context['native_language_sources']
    assert 'theguardian.com/football' not in context['native_language_sources']


def test_missing_key_defaults_to_empty(monkeypatch, tmp_path):
    from src.static import sources
    monkeypatch.setattr(sources, '_load_config', lambda name: dict(BASE))
    assert sources.get_config('anything')['native_language_sources'] == set()


def test_non_list_value_is_rejected(monkeypatch):
    from src.static import sources
    bad = dict(BASE, native_language_sources='zerozero.pt')
    monkeypatch.setattr(sources, '_load_config', lambda name: bad)
    with pytest.raises(ValueError, match='native_language_sources'):
        sources.get_config('anything')


@pytest.mark.asyncio
@pytest.mark.parametrize('source,expect_translate', [
    ('zerozero.pt', False),
    ('bbc.com/football', True),
])
async def test_serve_skips_translation_for_native_sources(monkeypatch, source, expect_translate):
    from src.processor import service

    translator = MagicMock()
    translator.translate = MagicMock(return_value='TRANSLATED')
    seen = {}

    def capture(*args, **kwargs):
        # serve() bails out right after the head is built; capture what it used.
        seen['text'] = args[0]
        return 'head'

    monkeypatch.setattr(service, 'make_head', capture)
    monkeypatch.setattr(service, 'is_ignored_prefix', lambda head: True)

    context = {
        'platforms': {Platform.FACEBOOK: True},
        'native_language_sources': {'zerozero.pt'},
    }
    await service.serve(
        client=AsyncMock(), graph=MagicMock(), nlp=MagicMock(), translator=translator,
        message_text='Lazio anuncia central apontado ao Benfica',
        handler_url_path=MagicMock(), posted_d={}, context=context, source=source,
    )

    assert translator.translate.called is expect_translate
    assert seen['text'] == ('TRANSLATED' if expect_translate else 'Lazio anuncia central apontado ao Benfica')
