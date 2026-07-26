import re
import logging
import unicodedata

logger = logging.getLogger('app')

# Food-каналы (recipe_only в конфиге) агрегируют кулинарные блоги и Telegram-каналы,
# где рецепты идут вперемешку с НЕ-рецептами: новости, подборки «melhores restaurantes»,
# огляди продуктів, акції/промо. В канал нужны только рецепты, поэтому запись проходит
# лишь при явных признаках рецепта в её тексте. Зеркало topic_filter (там наоборот —
# ОТСЕКАЕМ не-футбол), только здесь ПРОПУСКАЕМ то, что похоже на рецепт.

# JSON-LD Recipe и разметка популярных recipe-плагинов — в полноконтентном RSS-теле
# WordPress/Blogger. Сильный однозначный сигнал: если карточка рецепта размечена, это
# рецепт вне зависимости от текста.
_RECIPE_SCHEMA_RE = re.compile(r'@type"?\s*:\s*"?recipe', re.IGNORECASE)
_RECIPE_MARKERS = (
    'wprm-recipe', 'tasty-recipe', 'mv-create', 'easyrecipe', 'hrecipe',
    'schema.org/recipe', 'wp-block-recipe', 'recipe-card',
)

# Секции карточки рецепта на PT-BR / PT-PT (проверяем по тексту со снятой диакритикой:
# «porções»->«porcoes», «preparação»->«preparacao», «confecção»->«confeccao»).
_INGREDIENTS_RE = re.compile(r'\bingredientes?\b')
_PREP_RE = re.compile(
    r'\bmodo de (?:preparo|fazer|preparar|confeccao|confecao)\b'
    r'|\bpreparo\b|\bpreparacao\b|\bconfeccao\b|\bconfecao\b|\bcomo (?:fazer|preparar)\b'
)
# Прямое «рецепт/рецепти» в заголовке или тексте — слабее секций, но в кулинарном блоге
# однозначно указывает на рецепт (или подборку рецептов).
_RECIPE_WORD_RE = re.compile(r'\breceitas?\b')

# --- слабый сигнал ТОЛЬКО для видео (см. is_recipe(video=True)) ---
# Видео-рецепты в Telegram часто идут с телеграфной подписью: название блюда и голый
# список ингредиентов, БЕЗ слов «Ingredientes»/«Modo de preparo»/«receita». Ценность
# такого поста — сам клип, поэтому для видео дополнительно принимаем список ингредиентов,
# распознанный ПО СТРУКТУРЕ. Промо/анонсы структуры списка не имеют и продолжают отсекаться.
_BULLET_RE = re.compile(r'^\s*(?:[-*•·➞▪]+|\d+\s*[.)])\s*')
# Мера объёма/веса/счёта: BR (xícara, colher, a gosto) и PT-PT (chávena, dl, q.b.).
_MEASURE_RE = re.compile(
    r'\b(colher(?:es)?|xicara(?:s)?|chavena(?:s)?|copo(?:s)?|caneca(?:s)?|dente(?:s)?'
    r'|pitada(?:s)?|lata(?:s)?|pacote(?:s)?|saqueta(?:s)?|envelope(?:s)?|unidade(?:s)?'
    r'|fatia(?:s)?|rodela(?:s)?|ramo(?:s)?|maco(?:s)?|folha(?:s)?|talo(?:s)?|cabeca(?:s)?'
    r'|punhado(?:s)?|gomo(?:s)?|tablete(?:s)?|kg|quilo(?:s)?|gramas?|gr|mg|ml|dl|cl'
    r'|litro(?:s)?)\b')
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


def is_recipe(*texts, video=False):
    # True, если хотя бы один из переданных фрагментов (заголовок, описание, тело статьи,
    # подпись Telegram) похож на рецепт. Проверки идут от сильного сигнала к слабому.
    # video=True — пост несёт видео: ценность в клипе, а не в подписи, поэтому вдобавок
    # принимаем список ингредиентов, распознанный по структуре (см. looks_like_ingredient_list).
    raw = '\n'.join(t for t in texts if t)
    if not raw:
        return False

    low = raw.lower()
    if _RECIPE_SCHEMA_RE.search(low) or any(marker in low for marker in _RECIPE_MARKERS):
        return True

    norm = _normalize(raw)
    if _INGREDIENTS_RE.search(norm) and _PREP_RE.search(norm):
        return True
    if _RECIPE_WORD_RE.search(norm):
        return True

    if video and looks_like_ingredient_list(raw):
        logger.debug("[RecipeFilter] video + ingredient-list structure -> pass")
        return True

    logger.debug("[RecipeFilter] no recipe markers -> skip")
    return False
