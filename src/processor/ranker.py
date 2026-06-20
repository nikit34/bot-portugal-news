from src.processor.caption_guard import clickbait_score

# Sweet-spot длины заголовка (символы): FB обрезает на ~125 и предсказывает dwell —
# слишком короткий заголовок недоинформативен, слишком длинный обрезается.
_LEN_LOW, _LEN_HIGH = 40, 90


def _length_bonus(head):
    n = len(head or '')
    if _LEN_LOW <= n <= _LEN_HIGH:
        return 1.0
    if n < _LEN_LOW:
        return n / _LEN_LOW
    return max(0.0, 1.0 - (n - _LEN_HIGH) / _LEN_HIGH)


def candidate_score(candidate, state, current_hour):
    # Scale-free скор кандидата для best-K отбора: выученный reward источника и часа
    # (нормированы на средний reward, поэтому ~1 для среднего, >1 для сильного, 0
    # при отсутствии данных — тогда решают эвристики) + бонус за длину заголовка в
    # sweet-spot − штраф за кликбейт. На холодном старте (нет выученных данных)
    # ранжирование чисто эвристическое; по мере накопления learned-член доминирует.
    head = candidate.get('head', '')
    source = candidate.get('source', '')
    text = candidate.get('text', '')
    sources = state.get('sources', {})
    hours = state.get('hours', {})

    scored = [e['reach_avg'] for e in sources.values() if e.get('n', 0) > 0]
    mean = sum(scored) / len(scored) if scored else 0.0

    def norm(bucket, key):
        entry = bucket.get(str(key))
        if entry and entry.get('n', 0) > 0 and mean > 0:
            return entry['reach_avg'] / mean
        return 0.0

    learned = norm(sources, source) + 0.5 * norm(hours, current_hour)
    return learned + _length_bonus(head) - clickbait_score(text)
