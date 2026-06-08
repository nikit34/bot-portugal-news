# Контент-фильтр: посты, где совпал любой паттерн, НЕ публикуются.
# Паттерны — regex по НОРМАЛИЗОВАННОМУ тексту (нижний регистр, без диакритики,
# с раскрытием обфускации @->a, 0->o, $->s и т.п.). Используйте границы слова \b,
# чтобы не ловить подстроки. Списки редактируемые — подгоняйте под свои нужды.

# Мат / обсценная лексика (PT-BR/PT-PT + EN)
PROFANITY = [
    r"\bcaralh\w*",        # caralho, car@lho (после нормализации)
    r"\bporras?\b",        # porra(s)
    r"\bfod[aei]\w*",      # foda, fode, foder, fodido, foda-se
    r"\bmerdas?\b",
    r"\bputas?\b",         # puta(s). NB: "puto" (PT-PT = пацан) намеренно НЕ блокируем
    r"\bputaria\b",
    r"\bbuceta\w*",
    r"\bcuz[ao]\w*",       # cuzao / cuzão
    r"\bcornos?\b",
    r"\bv[ie]ados?\b",     # viado / veado (гомофобное)
    r"\bpqp\b", r"\bvtnc\b", r"\bfdp\b", r"\bvsf\b",
    r"\bfuck\w*", r"\bshit\w*", r"\bbullshit\b", r"\bbitch\w*", r"\bcunt\b", r"\basshole\b",
]

# Слуры (расистские/гомофобные) — блокировать жёстко. Дополняйте осторожно (FP!).
SLURS = [
    r"\bnigg\w*", r"\bfaggot\w*", r"\bretard\w*",
]

# Реклама / гемблинг / спам-зазывы (частая причина банов)
ADS_GAMBLING = [
    r"\baposta\w*", r"\baposte\b",        # агрессивно: может задеть новости про ставки
    r"\bbet365\b", r"\b1xbet\b", r"\bbetano\b", r"\bblaze\b",
    r"\bsportingbet\b", r"\bbetfair\b", r"\bsuperbet\b", r"\bestrelabet\b",
    r"\bcassino\b", r"\bcasino\b",
    r"\bbonus\b",                         # bônus -> bonus после снятия диакритики
    r"\bcodigo\s+promocional\b",
    r"\bpromo\s*code\b",
    r"\blink\s+na\s+bio\b",
    r"\bclique\s+(aqui|no\s+link)\b",
    r"\bganh[ae]\s+(dinheiro|ate|r?\$)",
]

BLOCKLIST = PROFANITY + SLURS + ADS_GAMBLING
