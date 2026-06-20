import re

# Библиотека ЖИВЫХ открытых вопросов (драйвер комментариев). FB ценит вдумчивые
# комменты выше лайков, а открытый вопрос НЕ является engagement-bait (в отличие
# от «comente SIM»). Гард зашит прямо сюда: ни один шаблон не содержит bait-фраз
# (есть тест test_cta), а сущность (клуб/игрок) подставляется в слот — так вопрос
# варьируется по статье, а не повторяется дословно (важно против спам-сигнала).
_TEMPLATES = [
    'E você, concorda com o que {entity} fez?',
    'O que achou da atuação de {entity}?',
    '{entity} mereceu? Deixe a sua análise nos comentários.',
    'Qual a sua opinião sobre {entity} nesta temporada?',
    'Foi a decisão certa para {entity}? Conte o que pensa.',
    '{entity}: acerto ou erro? Queremos saber a sua leitura.',
    'Como avalia o momento de {entity}?',
    'Concorda com a análise sobre {entity}?',
]

_ENTITY_LABELS = ('ORG', 'PER')
# Запрещённые формулировки — гарантия, что библиотека НЕ скатывается в bait.
_FORBIDDEN = re.compile(
    r'comente\s+(sim|nao)|marque\s+um\s+amigo|compartilh|curta\s+se|tag a friend|like if',
    re.IGNORECASE,
)


def build_cta(doc):
    # Берём первую сущность ORG/PER как якорь; детерминированно (без random/Date —
    # они недоступны/ломают воспроизводимость) выбираем шаблон по хешу её текста,
    # чтобы вопрос менялся между постами. Нет сущности => нет CTA (не лепим
    # обобщённый робо-вопрос на низко-сущностный пост).
    entities = [ent.text for ent in getattr(doc, 'ents', [])
                if getattr(ent, 'label_', '') in _ENTITY_LABELS]
    if not entities:
        return ''
    entity = entities[0]
    idx = sum(ord(c) for c in entity) % len(_TEMPLATES)
    return _TEMPLATES[idx].format(entity=entity)
