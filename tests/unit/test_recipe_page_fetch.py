from collections import deque

import httpx
import pytest

import src.parsers.rss.parser as rss
from src.processor.history_comparator import make_head
from src.static.sources import Platform

# Страница записи тизерного фида: в RSS был только анонс, рецепт есть на самой странице.
RECIPE_PAGE = """
<html><head><title>Dadinho de Tapioca</title></head><body>
<aside><div class="wprm-recipe-ingredient">2 ovos</div></aside>
<article><h2>Ingredientes:</h2>
<ul><li>500 g de tapioca granulada</li><li>500 ml de leite</li><li>2 colheres de sopa de manteiga</li></ul>
<h2>Modo de preparo:</h2><ol><li>Ferva o leite e misture a tapioca.</li></ol></article>
</body></html>
"""

# Страница-подборка категории: карточки чужих рецептов в блоках, своей секции нет.
COLLECTION_PAGE = """
<html><body><h1>Assados: tão práticos e suculentos!</h1>
<p>Com as nossas receitas o sucesso é garantido: chamuças de alheira no forno,
frango assado com manteiga, 2 kg de batatas, 1 colher de sopa de azeite, 200 g de queijo.</p>
<div class="wprm-recipe-container"><a class="wprm-recipe-link">Ver receita</a></div>
</body></html>
"""

TEASER_ENTRY = {'title': 'Dadinho de Tapioca', 'link': 'https://blog.example/receitas/dadinho/',
                'summary': 'O dadinho de tapioca é uma iguaria tipicamente brasileira.'}


def _mock_page(monkeypatch, text, status=200, raise_on_get=None):
    requested = []

    class _Response:
        status_code = status

        def __init__(self):
            self.text = text

        def raise_for_status(self):
            if status >= 400:
                raise httpx.HTTPStatusError('boom', request=None, response=None)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            requested.append(url)
            if raise_on_get:
                raise raise_on_get
            return _Response()

    monkeypatch.setattr(rss.httpx, 'AsyncClient', _Client)
    return requested


@pytest.fixture(autouse=True)
def _reset_budget(monkeypatch):
    rss._page_fetch_count = 0
    monkeypatch.setattr(rss, 'RECIPE_PAGE_FETCH_ENABLED', True)
    monkeypatch.setattr(rss, 'RECIPE_PAGE_FETCH_MAX_PER_RUN', 25)


async def test_recipe_recovered_from_entry_page(monkeypatch):
    requested = _mock_page(monkeypatch, RECIPE_PAGE)

    assert await rss._entry_page_has_recipe(TEASER_ENTRY, 'receitasdemae') is True
    assert requested == ['https://blog.example/receitas/dadinho/']


async def test_collection_page_is_not_a_recipe(monkeypatch):
    # На целой странице разметке карточек не верим: своей секции ингредиентов нет.
    _mock_page(monkeypatch, COLLECTION_PAGE)

    entry = {'title': 'Assados: tão práticos e suculentos!', 'link': 'https://blog.example/assados/'}
    assert await rss._entry_page_has_recipe(entry, 'teleculinaria') is False


async def test_network_error_is_fail_closed(monkeypatch):
    _mock_page(monkeypatch, RECIPE_PAGE, raise_on_get=httpx.ConnectError('down'))

    assert await rss._entry_page_has_recipe(TEASER_ENTRY, 'receitasja') is False


async def test_http_error_is_fail_closed(monkeypatch):
    _mock_page(monkeypatch, RECIPE_PAGE, status=403)

    assert await rss._entry_page_has_recipe(TEASER_ENTRY, 'receitasja') is False


async def test_entry_without_link_is_not_fetched(monkeypatch):
    requested = _mock_page(monkeypatch, RECIPE_PAGE)

    assert await rss._entry_page_has_recipe({'title': 'Bolo'}, 'src') is False
    assert requested == []


async def test_fetch_disabled_by_flag(monkeypatch):
    requested = _mock_page(monkeypatch, RECIPE_PAGE)
    monkeypatch.setattr(rss, 'RECIPE_PAGE_FETCH_ENABLED', False)

    assert await rss._entry_page_has_recipe(TEASER_ENTRY, 'src') is False
    assert requested == []


def test_already_published_entry_is_recognised():
    # Фид отдаёт записи от старых к новым, поэтому бюджет дозагрузок нельзя тратить на
    # то, что уже опубликовано: ключ должен совпасть с ключом дедупа из serve.
    context = {'platforms': {Platform.ALL: None, Platform.FACEBOOK: True, Platform.INSTAGRAM: True}}
    posted = deque([[make_head('Dadinho de Tapioca O dadinho de tapioca é uma iguaria tipicamente '
                               'brasileira que se tornou presença marcante'),
                     {Platform.FACEBOOK, Platform.INSTAGRAM}]])
    published = {'title': 'Dadinho de Tapioca',
                 'summary': '<p>O dadinho de tapioca é uma iguaria tipicamente brasileira que se '
                            'tornou presença.</p>'}
    fresh = {'title': 'Bolo de Milho com Canela',
             'summary': '<p>Uma receita fofinha para o café da tarde com canela.</p>'}

    assert rss._already_published(published, posted, context) is True
    assert rss._already_published(fresh, posted, context) is False


async def test_per_run_budget_caps_fetches(monkeypatch):
    requested = _mock_page(monkeypatch, RECIPE_PAGE)
    monkeypatch.setattr(rss, 'RECIPE_PAGE_FETCH_MAX_PER_RUN', 2)

    for _ in range(4):
        await rss._entry_page_has_recipe(TEASER_ENTRY, 'src')

    assert len(requested) == 2
