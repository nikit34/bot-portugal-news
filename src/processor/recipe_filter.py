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


def _normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in text if not unicodedata.combining(char))


def is_recipe(*texts):
    # True, если хотя бы один из переданных фрагментов (заголовок, описание, тело статьи,
    # подпись Telegram) похож на рецепт. Проверки идут от сильного сигнала к слабому.
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

    logger.debug("[RecipeFilter] no recipe markers -> skip")
    return False
