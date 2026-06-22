import re

from src.static.settings import CTA_EMISSION_RATE

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
    'Que nota você dá para {entity} aqui?',
    'O que {entity} precisa de mudar, na sua opinião?',
    'Surpreendido com {entity}? Diga o que sentiu.',
    'Na sua leitura, isto valoriza ou prejudica {entity}?',
    'Qual o próximo passo de {entity}, na sua visão?',
    '{entity} está no caminho certo? Argumente.',
    'Você confia em {entity} para o que vem aí?',
    'Justo ou exagerado o que se diz sobre {entity}?',
    'Como você teria resolvido isto no lugar de {entity}?',
    'Esse resultado muda a sua opinião sobre {entity}?',
    'O que mais te marcou em {entity} aqui?',
    'Dá para defender {entity} nesta? Conte.',
    'Que expectativa você tem para {entity} agora?',
    'Concorda que isto define a temporada de {entity}?',
    'Ponto alto ou ponto baixo para {entity}? Explique.',
    'Você apostaria em {entity} depois disto?',
]

_ENTITY_LABELS = ('ORG', 'PER')
# Запрещённые формулировки — гарантия, что библиотека НЕ скатывается в bait.
_FORBIDDEN = re.compile(
    r'comente\s+(sim|nao)|marque\s+um\s+amigo|compartilh|curta\s+se|tag a friend|like if',
    re.IGNORECASE,
)


def build_cta(doc):
    # Берём первую сущность ORG/PER как якорь; детерминированно (без random/Date —
    # они недоступны/ломают воспроизводимость) выбираем шаблон по хешу ТЕКСТА ПОСТА,
    # а не сущности — так один и тот же повторяющийся клуб (Benfica и т.п.) получает
    # РАЗНЫЙ вопрос в разных постах, что снимает дословные повторы (главный риск
    # демоута). Нет сущности => нет CTA (не лепим робо-вопрос на низко-сущностный пост).
    entities = [ent.text for ent in getattr(doc, 'ents', [])
                if getattr(ent, 'label_', '') in _ENTITY_LABELS]
    if not entities:
        return ''
    entity = entities[0]
    seed = getattr(doc, 'text', None) or entity
    seed_val = sum(ord(c) for c in seed)
    # Дробный гейт: пропускаем CTA только на доле постов (детерминированно по seed).
    if (seed_val % 100) >= round(CTA_EMISSION_RATE * 100):
        return ''
    idx = seed_val % len(_TEMPLATES)
    return _TEMPLATES[idx].format(entity=entity)
