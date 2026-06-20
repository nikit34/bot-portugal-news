# Паттерны кликбейта и engagement-bait для caption_guard. Матчатся по
# НОРМАЛИЗОВАННОЙ форме подписи (content_filter._normalize: нижний регистр, снятая
# диакритика, разраскрытый leet, схлопнутые повторы) — поэтому пишем их БЕЗ акцентов
# и в нижнем регистре. Цель — целые фразы и CTA-императивы (а не одиночные
# эмоциональные слова), чтобы не резать легитимные заголовки.
#
# PT идёт первым намеренно: подписи переводятся на португальский ДО продюсеров,
# поэтому английские паттерны срабатывают редко (но оставлены — часть источников EN).

# CTA-bait: прямые призывы «прокомментируй/отметь/поделись/подпишись». Строка,
# матчнутая этими паттернами, вырезается целиком (это самостоятельный мусор).
CTA_BAIT = [
    # --- PT ---
    r'\bcoment[ae]\w*\b.{0,15}\b(sim|nao|abaixo|aqui|isso)\b',
    r'\bmarqu\w+\b.{0,15}\b(um |dois )?amig',
    r'\bmarqu\w+\b.{0,15}\balguem\b',
    r'\bcompartilh\w+',
    r'\bcurt[ae]\b.{0,15}\b(a pagina|se|aqui|isso)\b',
    r'\bdeix\w+\b.{0,12}\b(seu )?like\b',
    r'\bsiga\b.{0,15}\b(a )?(pagina|nos|nossa)\b',
    r'\binscreva-?se\b',
    r'\bativ\w+\b.{0,15}\bnotificac',
    # --- EN ---
    r'\btag (a|your) ?\w*friend',
    r'\bcomment\b.{0,12}\b(yes|no|below|if)\b',
    r'\blike if\b',
    r'\bshare if\b',
    r'\bshare to (win|enter)\b',
    r'\bdouble tap\b',
    r'\bfollow (for|us)\b',
    r'\bsmash (that|the) like\b',
    r'\bhit (the|that) like\b',
]

# Кликбейт-фразы (curiosity gap). Не вырезаем (могут вести реальный заголовок), но
# учитываем в clickbait_score — чтобы ранкер опускал такие посты ниже.
CLICKBAIT = [
    # --- PT ---
    r'\b(voce |tu )?nao va[is] acreditar\b',
    r'\bvai te surpreender\b',
    r'\bo que aconteceu (a |em )?seguir\b',
    r'\bnunca va[is] adivinhar\b',
    r'\bde queixo caido\b',
    r'\bvai deixar\b.{0,15}\bchocado',
    r'\bisto (vai|e) (incrivel|inacreditavel)\b',
    # --- EN ---
    r'\byou wo?n.?t believe\b',
    r'\bwhat happened next\b',
    r'\bwill blow your mind\b',
    r'\bwait for it\b',
    r'\bnumber \d+ will (shock|surprise)\b',
]
