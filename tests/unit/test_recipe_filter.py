import pytest

from src.processor.recipe_filter import is_recipe, looks_like_ingredient_list


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


# --- video=True: слабый структурный сигнал ---

# Реальная подпись видео-рецепта из @Brasil_Receitas: название блюда + голый список
# ингредиентов, БЕЗ слов "Ingredientes"/"Modo de preparo"/"receita".
TERSE_VIDEO_CAPTION = """Sanduíche de carne

* 1,5 kg de acém
* 1 cebola
* 4 dentes de alho
* 1 tomate
* 1 colher de chá de Páprica picante
* 2 colheres de sopa de shoyu
* Sal
* Salsinha a gosto"""

# Тоже реальная: болтовня про блюдо без списка — клип есть, но рецепта в подписи нет.
CHATTY_VIDEO_CAPTION = (
    'bença. A semana começou e é dia de caldo de cabeça de galo.\n\n'
    'Começar a semana forte pra pegar uns leões pelo caminho, né? Então faz esse caldo, visse?\n\n'
    'Boa semana.'
)

PROMO_VIDEO_CAPTION = (
    'Aproveite! Desconto de 50% só hoje na nossa loja.\n'
    'Corre que é por tempo limitado, link na bio!'
)


def test_terse_video_caption_passes_only_as_video():
    # Без видео телеграфная подпись не проходит (как и раньше) — с видео проходит.
    assert is_recipe(TERSE_VIDEO_CAPTION) is False
    assert is_recipe(TERSE_VIDEO_CAPTION, video=True) is True


def test_chatty_video_caption_still_dropped():
    # Ослабление не значит «пропускать любое видео»: структуры списка тут нет.
    assert is_recipe(CHATTY_VIDEO_CAPTION, video=True) is False


def test_promo_video_caption_still_dropped():
    assert is_recipe(PROMO_VIDEO_CAPTION, video=True) is False


def test_video_flag_does_not_weaken_non_video_path():
    # Дефолт video=False сохраняет прежнее поведение для всех фото/RSS-записей.
    for text in NOT_RECIPES:
        assert is_recipe(text) is False


def test_recipes_still_pass_with_video_flag():
    for text in RECIPES:
        assert is_recipe(text, video=True) is True


def test_ingredient_list_needs_quantities_and_volume():
    # PT-PT меры (chávena, dl, q.b.) тоже считаются.
    assert looks_like_ingredient_list(
        '2 chávenas de farinha\n1 dl de leite\nSal q.b.') is True
    # Одной строки с количеством мало (порог по двум осям).
    assert looks_like_ingredient_list('2 ovos') is False
    # Проза с числами, но без столбика коротких строк — не список.
    assert looks_like_ingredient_list(
        'Estudo com 2000 pessoas mostrou que quem cozinha em casa gasta 30% menos '
        'dinheiro com alimentacao ao longo de um ano inteiro.') is False
    assert looks_like_ingredient_list('') is False
