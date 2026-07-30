import pytest

from src.processor.recipe_filter import (
    is_collection, is_recipe, looks_like_ingredient_list, looks_quantified)


# Real-ish recipe posts from the BR/PT food blogs the food channel aggregates.
RECIPES = [
    # Full recipe body with ingredients + preparation sections.
    'Bolo de cenoura fofinho\nIngredientes: 3 cenouras, 4 ovos, 2 xícaras de açúcar.\n'
    'Modo de preparo: bata tudo no liquidificador e leve ao forno.',
    # PT-PT wording (accents + "confecção" / "porções").
    'Bacalhau à Brás\nIngredientes para 4 porções:\nModo de confecção: desfie o bacalhau...',
    # Секции в заголовках HTML, как в полноконтентных WordPress-фидах.
    'Picolé caseiro de frutas\n<h2>Ingredientes da receita de picolé caseiro</h2>'
    '<h2><span id="modo_de_preparo">Modo de preparo</span></h2><ol><li>bata a fruta...</li></ol>',
    # Размеченная карточка рецепта (WordPress Recipe Maker): ингредиенты/шаги внутри.
    'Frango assado <div class="wprm-recipe-ingredient">2 kg de frango</div>',
    # JSON-LD Recipe schema.
    'Torta de limão <script type="application/ld+json">{"@type":"Recipe","name":"Torta"}</script>',
    # Рецепт одним абзацем: секция + количества прозой (плюс опечатка «INGREDINTES»).
    'BOLO DE NOZ\nINGREDINTES: 8 ovos, 250g de açucar, 250g de nozes, 1 colher de farinha.\n'
    'CONFECÇÃO: bate-se as gemas com o açucar, vai ao forno brando.',
    # Старый кулинарный блог: рецепт прозой, введённый строкой «Receita:».
    'Podim de chocolate.\nReceita: "Batem-se bem doze ovos com quinhentas grammas de assucar '
    'e mistura-se com meio pão de chocolate desfeito em agua. Depois vae ao forno."',
]

# Food-adjacent posts that are NOT recipes and must be dropped.
NOT_RECIPES = [
    'Os 10 melhores restaurantes de Lisboa para visitar em 2026',
    'Chef renomado abre novo espaço no centro do Rio',
    'Preços dos alimentos sobem 8% no último trimestre, diz pesquisa',
    'Conheça a história do café brasileiro e sua exportação',
    'Novo aplicativo de delivery chega a São Paulo nesta semana',
    # Анонс/тизер записи блога: про блюдо, но самого рецепта в посте нет.
    'Feijoada de Frutos do Mar\nAs receitas culinárias com Frutos do Mar estão ganhando cada '
    'vez mais adeptos. Os Frutos do Mar são alimentos que oferecem beneficios à saúde [...]',
    # Слово «receita» в заголовке без самого рецепта - не рецепт.
    'Receita de brigadeiro gourmet para a festa',
]

# Подборки, меню недели и статьи-сравнения: рецепты внутри страницы есть (и разметка
# карточек тоже), но САМ ПОСТ - не рецепт, поэтому отсекаем по форме заголовка.
COLLECTIONS = [
    'As 10 melhores receitas de verão para refrescar\nIngredientes: ...\nModo de preparo: ...',
    'Doces preferidos dos portugueses (6 receitas)\nIngredientes:\nModo de preparo:',
    'Receitas fáceis para o dia a dia (6 sugestões)\nIngredientes:\nModo de preparo:',
    'Acompanhamentos para Churrasco: Nossa Seleção das Melhores Receitas\n'
    '<div class="wprm-recipe-ingredient">2 kg de arroz</div>',
    'Menu semanal #290\nSegunda-feira: sopa de abóbora. Terça-feira: filetes de cavala.',
    'Cozinhando sob pressão: panela elétrica ou convencional, qual a melhor para sua cozinha?\n'
    '<div class="wprm-recipe-ingredient">1 kg de feijão</div>',
]


@pytest.mark.parametrize('text', RECIPES)
def test_recipes_pass(text):
    assert is_recipe(text) is True


@pytest.mark.parametrize('text', NOT_RECIPES)
def test_non_recipes_are_dropped(text):
    assert is_recipe(text) is False


@pytest.mark.parametrize('text', COLLECTIONS)
def test_collections_and_menus_are_dropped(text):
    # Форма заголовка перебивает даже разметку рецепта на странице.
    assert is_recipe(text) is False


def test_roundup_markup_is_dropped():
    # Плагин размечает подборку рецептов (wprm-recipe-roundup-item) - это список ссылок.
    assert is_recipe(
        'Sobremesas para o fim de semana',
        '<div class="wprm-recipe-roundup-item"><a class="wprm-recipe-link">Bolo</a></div>'
        '<div class="wprm-recipe-ingredient">2 ovos</div>') is False


def test_section_words_in_prose_are_not_enough():
    # Статья про продукт: слова «ingrediente»/«preparação» есть, но не как секции рецепта.
    assert is_recipe(
        'Aloé Vera: da cozinha antiga aos superfoods de hoje',
        'A aloé vera é um excelente ingrediente em detergentes e pode ser utilizada na '
        'confecção de geleias. Para os usos culinários é fundamental a correta preparação '
        'do gel, removendo cuidadosamente a casca antes de servir aos convidados.') is False


def test_ingredients_without_preparation_is_not_enough():
    # Одного упоминания «ingredientes» без способа приготовления мало (напр. новость
    # про качество ингредиентов), нужны обе секции.
    assert is_recipe('Estudo avalia os ingredientes dos ultraprocessados') is False


def test_signal_can_come_from_any_fragment():
    # is_recipe(*texts): срабатывает, если рецепт виден хотя бы в одном фрагменте
    # (заголовок чистый, тело — с разметкой карточки рецепта).
    assert is_recipe('Título neutro', '<div class="wprm-recipe-ingredient">2 ovos</div>') is True


def test_recipe_container_class_alone_is_not_enough():
    # Общий класс-контейнер темы (wprm-recipe / recipe-card) висит на КАЖДОЙ странице
    # блога, в том числе в блоке «похожие рецепты» у статьи, поэтому сам по себе не считается.
    assert is_recipe('Panela de pressão: o que saber antes de comprar',
                     '<div class="wprm-recipe-container">...</div>') is False


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


def test_collections_still_dropped_with_video_flag():
    for text in COLLECTIONS:
        assert is_recipe(text, video=True) is False


# Реальные подписи из @Brasil_Receitas: канал шлёт и рецепты, и рекламу магазина, и
# reels-тизеры без рецепта. Раньше все три проходили (в тексте есть слово «receita»).
TG_VIDEO_RECIPES = [
    # Ингредиенты одной строкой, без двоеточия после слова.
    'Sabia que fazer churros em casa é mais fácil que você imagina? Ingredientes  1 xícara de '
    'leite (xícara de 240ml) 1 colher de sopa generosa de manteiga  2 colheres de sopa de açúcar',
    # Список ингредиентов в строку через bullet-символы.
    'Panceta ao molho oriental\n\n• Açúcar mascavo 4 colheres de sopa • Shoyu 3 colheres de sopa '
    '• Molho de ostra 2 colheres de sopa • Alho 5 dentes picados',
]

TG_VIDEO_NOT_RECIPES = [
    # Реклама магазина: «receita» упомянута, рецепта нет.
    'Vocês pediram e está aí a receita do melhor bolo de fubá cremoso da vida! Feito com Queijo '
    'Artesanal Céu de Minas. Inclusive fizemos o kit TRADIÇÃO MINEIRA, disponível na loja física '
    'e virtual pelo site www.ceudeminas.com.br Enviamos para todo Brasil. #ceudeminas',
    # Reels-тизер: одна фраза и хэштеги.
    'Quando faço arroz com linguiça assim nao sobra nada 😋 #receitas #foryou #reels #viral',
    'RECEITA DE CUSCUZ COM GOIABADA E QUEIJO😋 FAÇA ESSA COMBINAÇÃO EN CASA E SE SURPREENDA '
    'COM O RESULTADO! #cuscuz #cuscuzdoce #cuscuzrecheado',
]


@pytest.mark.parametrize('text', TG_VIDEO_RECIPES)
def test_real_telegram_video_recipes_pass(text):
    assert is_recipe(text, video=True) is True


@pytest.mark.parametrize('text', TG_VIDEO_NOT_RECIPES)
def test_real_telegram_posts_without_recipe_are_dropped(text):
    assert is_recipe(text, video=True) is False


# --- full_page=True: гейт по дозагруженной странице записи (тизерные фиды) ---

# У целой страницы в сайдбаре висят карточки чужих рецептов, поэтому разметки и мер
# по странице недостаточно: нужна секция ингредиентов самой записи.
PAGE_WITH_RECIPE = (
    '<aside><div class="wprm-recipe-ingredient">2 ovos</div></aside>'
    '<article><h2>Ingredientes:</h2><ul><li>500 g de tapioca</li><li>500 ml de leite</li>'
    '<li>2 colheres de sopa de manteiga</li></ul>'
    '<h2>Modo de preparo:</h2><ol><li>Ferva o leite.</li></ol></article>')

PAGE_WITHOUT_RECIPE = (
    '<h1>Assados: tão práticos e suculentos!</h1><p>Com as nossas receitas o sucesso é '
    'garantido: 2 kg de batatas, 1 colher de sopa de azeite, 200 g de queijo.</p>'
    '<aside><div class="wprm-recipe-ingredient">2 ovos</div></aside>')


def test_full_page_with_own_recipe_section_passes():
    assert is_recipe('Dadinho de Tapioca', PAGE_WITH_RECIPE, full_page=True) is True


def test_full_page_without_own_recipe_section_is_dropped():
    assert is_recipe('Assados: tão práticos e suculentos!', PAGE_WITHOUT_RECIPE,
                     full_page=True) is False
    # Контраст: в теле фида (full_page=False) разметке карточки верим, и тот же HTML
    # прошёл бы по чужой карточке из сайдбара.
    assert is_recipe('Assados: tão práticos e suculentos!', PAGE_WITHOUT_RECIPE) is True


def test_full_page_still_respects_collection_headline():
    assert is_recipe('Doces preferidos dos portugueses (6 receitas)', PAGE_WITH_RECIPE,
                     full_page=True) is False


def test_is_collection_headline():
    assert is_collection('Menu semanal #290') is True
    assert is_collection('Receitas fáceis para o dia a dia (6 sugestões)') is True
    assert is_collection('Panela elétrica ou convencional, qual a melhor?') is True
    assert is_collection('Bolo de cenoura fofinho') is False


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


def test_looks_quantified_counts_measures_in_prose():
    # Рецепт одной строкой: количеств с мерами хватает (порог _MIN_QTY_MEASURES).
    assert looks_quantified('8 ovos, 250g de açucar, 250g de nozes, 1 colher de farinha') is True
    # Статья с числами, но без мер.
    assert looks_quantified('Estudo com 2000 pessoas mostra que 30% cozinham menos') is False
    assert looks_quantified('') is False
