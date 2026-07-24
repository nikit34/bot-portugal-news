import pytest

from src.processor.recipe_filter import is_recipe


# Real-ish recipe posts from the BR/PT food blogs the food channel aggregates.
RECIPES = [
    # Full recipe body with ingredients + preparation sections.
    'Bolo de cenoura fofinho\nIngredientes: 3 cenouras, 4 ovos, 2 xícaras de açúcar.\n'
    'Modo de preparo: bata tudo no liquidificador e leve ao forno.',
    # PT-PT wording (accents + "confecção" / "porções").
    'Bacalhau à Brás\nIngredientes para 4 porções.\nModo de confecção: desfie o bacalhau...',
    # Only the recipe schema markup present (WordPress Recipe Maker).
    'Frango assado <div class="wprm-recipe-container">...</div>',
    # JSON-LD Recipe schema.
    'Torta de limão <script type="application/ld+json">{"@type":"Recipe","name":"Torta"}</script>',
    # Weak but valid signal: the word "receita" in the title.
    'Receita de brigadeiro gourmet para a festa',
    'As 10 melhores receitas de verão para refrescar',
]

# Food-adjacent posts that are NOT recipes and must be dropped.
NOT_RECIPES = [
    'Os 10 melhores restaurantes de Lisboa para visitar em 2026',
    'Chef renomado abre novo espaço no centro do Rio',
    'Preços dos alimentos sobem 8% no último trimestre, diz pesquisa',
    'Conheça a história do café brasileiro e sua exportação',
    'Novo aplicativo de delivery chega a São Paulo nesta semana',
]


@pytest.mark.parametrize('text', RECIPES)
def test_recipes_pass(text):
    assert is_recipe(text) is True


@pytest.mark.parametrize('text', NOT_RECIPES)
def test_non_recipes_are_dropped(text):
    assert is_recipe(text) is False


def test_ingredients_without_preparation_is_not_enough():
    # Одного упоминания «ingredientes» без способа приготовления мало (напр. новость
    # про качество ингредиентов), нужны обе секции.
    assert is_recipe('Estudo avalia os ingredientes dos ultraprocessados') is False


def test_signal_can_come_from_any_fragment():
    # is_recipe(*texts): срабатывает, если рецептом пахнет хотя бы один фрагмент
    # (заголовок чистый, тело — с разметкой рецепта).
    assert is_recipe('Título neutro', '<div class="wprm-recipe">...</div>') is True


def test_empty_input():
    assert is_recipe() is False
    assert is_recipe('', None) is False
