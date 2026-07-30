import re
import logging
import unicodedata

logger = logging.getLogger('app')

# Food-каналы (recipe_only в конфиге) агрегируют кулинарные блоги и Telegram-каналы,
# где рецепты идут вперемешку с НЕ-рецептами: статьи и подборки, обзоры техники,
# истории блюд, новости про рестораны, промо. В канал нужны ТОЛЬКО рецепты, поэтому
# запись проходит лишь тогда, когда рецепт есть В САМОМ ТЕКСТЕ записи: ингредиенты +
# способ приготовления (или размеченная карточка рецепта). Зеркало topic_filter (там
# наоборот - ОТСЕКАЕМ не-футбол), только здесь ПРОПУСКАЕМ то, в чём виден рецепт.
#
# Почему одного слова «receita» НЕ хватает (так было раньше): в кулинарном блоге оно
# есть в имени сайта, в ссылке (/receitas/...), в футере «veja mais receitas» и в
# анонсе категории, т.е. гейт пропускал вообще любую запись такого фида - включая
# статьи «A verdadeira história do caldo verde» и подборки «(6 receitas)».

# --- сильный сигнал: разметка карточки рецепта ---
# JSON-LD Recipe и microdata schema.org/Recipe: страница ЯВЛЯЕТСЯ рецептом.
_RECIPE_SCHEMA_RE = re.compile(
    r'@type"?\s*:\s*"?recipe|schema\.org/recipe', re.IGNORECASE)
# Классы плагинов-рецептов, но именно те, что рендерятся ВНУТРИ карточки (ингредиент/
# шаг). Общий класс-контейнер (wprm-recipe, tasty-recipe, recipe-card) тема кладёт на
# каждую страницу - в блоке «похожие рецепты» его десятки даже в статье про кастрюли,
# поэтому сам по себе он ничего не значит.
_RECIPE_CARD_RE = re.compile(
    r'wprm-recipe-ingredient|wprm-recipe-instruction'
    r'|tasty-recipes-ingredient|tasty-recipes-instruction'
    r'|mv-create-ingredients|mv-create-instructions'
    r'|recipe-card__ingredient|easyrecipe.{0,40}ingredient'
    r'|class="ingredient"', re.IGNORECASE)   # hrecipe-микроформат
# Подборка рецептов, размеченная плагином (wprm-recipe-roundup-item): рецепты внутри
# есть, но пост - список ссылок, а не рецепт.
_ROUNDUP_MARKUP_RE = re.compile(r'recipe-roundup', re.IGNORECASE)

# Секции карточки рецепта на PT-BR / PT-PT (проверяем по тексту со снятой диакритикой:
# «porções»->«porcoes», «preparação»->«preparacao», «confecção»->«confeccao»).
# Ключевое: слово должно стоять КАК ЗАГОЛОВОК СЕКЦИИ - в начале строки, сразу после
# открывающего тега («<h2>Ingredientes da receita</h2>»), либо с двоеточием / закрытием
# тега / концом строки после него («Ingredientes:», «<b>Método</b>»). То же слово в прозе
# («um excelente ingrediente em detergentes», «na preparação de alimentos») - признак
# СТАТЬИ про продукт, а не рецепта, и такие записи раньше пролезали в канал.
def _section_pattern(words):
    # `\s+\d` в конце: «Ingredientes  1 xícara de leite» - список идёт сразу за словом,
    # без двоеточия (частая форма подписей в Telegram).
    return (r'(?:(?:^|>)\s*(?:' + words + r')\b'
            r'|\b(?:' + words + r')\s*(?::|</|$|\s\d))')


# `ingred\w*` вместо точного «ingredientes» - в блогах регулярны опечатки вроде
# «INGREDINTES», а слов на «ingred-» кроме ингредиента в тексте не бывает.
_INGREDIENTS_RE = re.compile(_section_pattern(r'ingred\w*'), re.MULTILINE)
_PREP_RE = re.compile(
    r'\bmodo de (?:preparo|fazer|preparar|confeccao|confecao)\b'
    r'|\bcomo (?:fazer|preparar)\b|\bpasso a passo\b|'
    + _section_pattern(r'preparo|preparacao|confeccao|confecao|metodo|instrucoes'),
    re.MULTILINE)
# Строка, которая ВВОДИТ рецепт: «Receita:», «Receita -». Старые кулинарные блоги так
# подают рецепт прозой, без секций. Футеры и имена сайтов такой формы не имеют.
_RECIPE_INTRO_RE = re.compile(r'^\s*receitas?\s*[:\-]', re.IGNORECASE | re.MULTILINE)

# --- НЕ рецепт по форме: подборка, меню недели, сравнение техники ---
# Проверяем только по ЗАГОЛОВКУ (первый фрагмент / первая строка подписи): в теле
# «10 melhores receitas» встречается в блоке «читайте также» у любого рецепта.
# Эти формы отсекаем ДАЖЕ при разметке рецепта на странице: у подборки карточки
# рецептов есть, но сам пост - не рецепт.
_COLLECTION_RE = re.compile(
    r'\(\s*\d+\s*(?:receitas?|sugestoes|ideias|opcoes)\s*\)'      # «(6 receitas)»
    r'|\b\d+\s+(?:melhores\s+)?(?:receitas|sugestoes|ideias|sobremesas|pratos)\b'
    r'|\bmelhores\s+receitas\b|\bselecao\s+d[ae]s?\b|\bcolecao\s+d[ae]s?\b'
    r'|\breceitas\s+(?:faceis|rapidas|simples|tradicionais|preferidas|classicas)\b'
    r'|\bmenu\s+(?:semanal|da\s+semana|#?\d+)\b|\bementa\s+semanal\b'
    r'|\bcardapio\s+(?:semanal|da\s+semana)\b'
    r'|\bqual\s+(?:a|o)\s+(?:melhor|pior)\b|\bvale\s+a\s+pena\b')

# --- слабый структурный сигнал: список ингредиентов ---
# Видео-рецепты в Telegram часто идут с телеграфной подписью: название блюда и голый
# список ингредиентов, БЕЗ слов «Ingredientes»/«Modo de preparo»/«receita». Ценность
# такого поста - сам клип, поэтому для видео дополнительно принимаем количества с мерами:
# столбиком (looks_like_ingredient_list) или в одну строку (looks_quantified). Промо,
# анонсы и болтовня столько мер не набирают и продолжают отсекаться.
_BULLET_RE = re.compile(r'^\s*(?:[-*•·➞▪]+|\d+\s*[.)])\s*')
# Мера объёма/веса/счёта: BR (xícara, colher, a gosto) и PT-PT (chávena, dl, q.b.).
_MEASURES = (
    r'colher(?:es)?|xicara(?:s)?|chavena(?:s)?|copo(?:s)?|caneca(?:s)?|dente(?:s)?'
    r'|pitada(?:s)?|lata(?:s)?|pacote(?:s)?|saqueta(?:s)?|envelope(?:s)?|unidade(?:s)?'
    r'|fatia(?:s)?|rodela(?:s)?|ramo(?:s)?|maco(?:s)?|folha(?:s)?|talo(?:s)?|cabeca(?:s)?'
    r'|punhado(?:s)?|gomo(?:s)?|tablete(?:s)?|kg|quilo(?:s)?|gramas?|gr|mg|ml|dl|cl'
    r'|litro(?:s)?')
_MEASURE_RE = re.compile(r'\b(?:' + _MEASURES + r')\b')
# «250g de açucar», «1 colher de sopa», «1/2 chávena de café» - количество с мерой.
# Рецепт прозой (без столбика строк) распознаём именно по числу таких мер.
_QTY_MEASURE_RE = re.compile(r'\b\d+(?:[.,/]\s?\d+)?\s*(?:' + _MEASURES + r'|g)\b')
_MIN_QTY_MEASURES = 3
_TO_TASTE_RE = re.compile(r'\ba gosto\b|\bq\.?\s?b\.?\b|\bquanto baste\b')
# Строка начинается с количества: «2 ovos», «1,5 kg ...», «1/2 colher ...».
_STARTS_QTY_RE = re.compile(r'^\d+(?:\s*[/.,]\s*\d+)?\s+\S')
# Строки списка ингредиентов короткие; проза длиннее и в подсчёт не попадает.
_INGREDIENT_LINE_MAX = 90
_MIN_INGREDIENT_LINES = 3
_MIN_QTY_LINES = 2


def _normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in text if not unicodedata.combining(char))


def looks_like_ingredient_list(text):
    # Структурный признак списка ингредиентов: несколько КОРОТКИХ строк с мерой
    # («2 colheres de açúcar»), количеством («3 bananas») или «a gosto»/«q.b.»,
    # из которых минимум _MIN_QTY_LINES начинаются с числа. Порог по двум осям сразу
    # держит промо-подписи снаружи: у них нет ни количеств, ни столбика коротких строк.
    ingredient_lines = 0
    qty_lines = 0
    for line in _normalize(text).splitlines():
        line = _BULLET_RE.sub('', line).strip()
        if not line or len(line) > _INGREDIENT_LINE_MAX:
            continue
        starts_qty = bool(_STARTS_QTY_RE.match(line))
        if starts_qty or _MEASURE_RE.search(line) or _TO_TASTE_RE.search(line):
            ingredient_lines += 1
            if starts_qty:
                qty_lines += 1
    return ingredient_lines >= _MIN_INGREDIENT_LINES and qty_lines >= _MIN_QTY_LINES


def looks_quantified(text):
    # Рецепт прозой: «8 ovos, 250g de açucar, 1 colher de farinha» - столбика строк
    # нет, но количеств с мерами несколько. Статьи и анонсы столько мер не набирают.
    return len(_QTY_MEASURE_RE.findall(_normalize(text))) >= _MIN_QTY_MEASURES


def is_collection(headline):
    # Подборка / меню недели / сравнение техники - по форме заголовка. Публичная, чтобы
    # RSS-парсер не тратил дозагрузку страницы на запись, которая всё равно отсеётся.
    match = _COLLECTION_RE.search(_normalize(headline))
    if match:
        logger.debug(f"[RecipeFilter] collection/menu headline (matched '{match.group(0)}') -> skip")
        return True
    return False


def _headline(texts):
    # Заголовок записи: у RSS это первый фрагмент (entry.title), у Telegram - первая
    # непустая строка подписи.
    for text in texts:
        if not text:
            continue
        for line in text.splitlines():
            if line.strip():
                return line.strip()
    return ''


def is_recipe(*texts, video=False, full_page=False):
    # True, если в переданных фрагментах (заголовок, описание, тело статьи, подпись
    # Telegram) виден САМ рецепт. Проверки идут от сильного сигнала к слабому.
    # video=True - пост несёт видео: ценность в клипе, а не в подписи, поэтому вдобавок
    # принимаем сами количества с мерами, без слов-секций (см. блок про видео выше).
    # full_page=True - на входе HTML целой страницы записи (дозагрузка для тизерных
    # фидов), к ней требования строже: см. ниже.
    raw = '\n'.join(t for t in texts if t)
    if not raw:
        return False

    if is_collection(_headline(texts)):
        return False

    low = raw.lower()
    if _ROUNDUP_MARKUP_RE.search(low):
        logger.debug("[RecipeFilter] recipe-roundup markup -> skip")
        return False

    norm = _normalize(raw)
    has_ingredients = bool(_INGREDIENTS_RE.search(norm))
    has_prep = bool(_PREP_RE.search(norm))
    has_quantities = looks_like_ingredient_list(raw) or looks_quantified(raw)

    if full_page:
        # У целой страницы в сайдбаре и в блоке «похожие рецепты» висят карточки ЧУЖИХ
        # рецептов (разметка, schema, даже слова секций), а мер по странице набирается
        # сколько угодно, поэтому этим сигналам по отдельности верить нельзя. Требуем
        # секцию ингредиентов + способ приготовления или сами количества. Проверено:
        # так проходят страницы рецептов тизерных фидов, но не подборки-категории
        # («Assados: tão práticos e suculentos!») и не статьи.
        if has_ingredients and (has_prep or has_quantities):
            return True
        logger.debug("[RecipeFilter] fetched page has no recipe sections -> skip")
        return False

    if _RECIPE_SCHEMA_RE.search(low) or _RECIPE_CARD_RE.search(low):
        return True
    if _RECIPE_INTRO_RE.search(norm):
        return True
    if has_ingredients and has_prep:
        return True
    # Одна из секций + сами количества: список ингредиентов столбиком либо несколько
    # мер в прозе. Так проходят рецепты без второй секции («Ingredientes» + список у
    # Bimby-блогов) и рецепты одним абзацем («CONFECÇÃO: ... 250g de açucar ...»).
    if (has_ingredients or has_prep) and has_quantities:
        return True

    if video and has_quantities:
        logger.debug("[RecipeFilter] video + ingredient quantities -> pass")
        return True

    logger.debug("[RecipeFilter] no recipe in the text -> skip")
    return False
