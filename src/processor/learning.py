import os
import json
import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger('app')


def _empty_state():
    return {'version': 1, 'pending': [], 'sources': {}, 'hours': {}, 'ig_quota': {'day': '', 'posts': 0}}


def load_state(path):
    # Robust load: a missing or corrupt state file must never break a run — the
    # learning model just cold-starts and re-accumulates.
    try:
        with open(path, 'r') as f:
            state = json.load(f)
        state.setdefault('version', 1)
        state.setdefault('pending', [])
        state.setdefault('sources', {})
        state.setdefault('hours', {})
        state.setdefault('ig_quota', {'day': '', 'posts': 0})
        return state
    except (FileNotFoundError, ValueError, OSError) as e:
        logger.info(f"[learning] no usable state at {path} ({e}); starting fresh")
        return _empty_state()


def ig_posts_today(state, today):
    quota = state.get('ig_quota') or {}
    return quota.get('posts', 0) if quota.get('day') == today else 0


def add_ig_posts(state, today, n):
    quota = state.setdefault('ig_quota', {'day': today, 'posts': 0})
    if quota.get('day') != today:
        quota['day'] = today
        quota['posts'] = 0
    quota['posts'] = quota.get('posts', 0) + n


def save_state(path, state):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write-then-rename so a crash/timeout mid-write can't leave a half JSON file.
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def record_publish(state, head, source, ts, **features):
    # Remember which source produced a just-published post so its reach can be
    # attributed back to that source once it matures (hours/days later, another run).
    # **features (fb_id, ig_id, is_video, hashtag_n) are stored only when provided,
    # so legacy pending entries / the reach-only path keep the minimal {head,source,ts}
    # shape. fb_id is the FB *page-post* id ({page}_{post}) needed by /{post-id}/insights.
    if not head or not source:
        return
    entry = {'head': head, 'source': source, 'ts': ts}
    for key, value in features.items():
        if value is not None:
            entry[key] = value
    state.setdefault('pending', []).append(entry)


def update_scores(state, reach_by_head, now, maturation_seconds, max_age_seconds, alpha):
    # Attribute matured reach to BOTH its source and its publish hour (EW-average),
    # drop scored/expired posts.
    pending = state.get('pending', [])
    sources = state.setdefault('sources', {})
    hours = state.setdefault('hours', {})
    dow_hours = state.setdefault('dow_hours', {})
    still_pending = []
    for post in pending:
        ts = post.get('ts', 0)
        age = now - ts
        head = post.get('head', '')
        reach = _reach_for(head, reach_by_head) if age >= maturation_seconds else None
        if reach is not None:
            _update_avg(sources, post.get('source', ''), reach, alpha)
            _update_avg(hours, _hour_of(ts), reach, alpha)
            _update_avg(dow_hours, _dow_hour_of(ts), reach, alpha)
        elif age < max_age_seconds:
            still_pending.append(post)
        # else: matured but never matched within max_age → prune (can't attribute)
    state['pending'] = still_pending
    return state


def reward_for(metrics, weights):
    # Engagement-weighted reward под сигналы ранжирования Meta 2026: раздача
    # (shares+sends), сохранения и досмотр весят тяжелее всего, лайки по умолчанию
    # обнулены, reach — хвост. metrics — dict с любыми из {reach, likes, comments,
    # shares, saves, watch}; отсутствующее считаем нулём (обратная совместимость со
    # старыми pending-записями и reach-only путём). watch — средний досмотр в секундах.
    return (
        weights.get('share', 0.0) * (metrics.get('shares') or 0)
        + weights.get('save', 0.0) * (metrics.get('saves') or 0)
        + weights.get('comment', 0.0) * (metrics.get('comments') or 0)
        + weights.get('watch', 0.0) * (metrics.get('watch') or 0)
        + weights.get('like', 0.0) * (metrics.get('likes') or 0)
        + weights.get('reach', 0.0) * (metrics.get('reach') or 0)
    )


def _bucket_hashtags(n):
    if n <= 0:
        return '0'
    return '1-3' if n <= 3 else '4+'


def update_scores_metrics(state, metrics_by_head, weights, now, maturation_seconds,
                          max_age_seconds, alpha, log_variants=False):
    # Reward-aware вариант update_scores: вместо чистого reach учитываем взвешенную
    # вовлечённость и дополнительно копим reward по формату (video/photo) и (опц.)
    # по числу хэштегов. Хранится в тех же {reach_avg, n} бакетах (имя ключа не
    # меняем, чтобы дайджест/top_sources работали без правок). Используется только
    # при LEARNING_REWARD_ENABLED — reach-путь (update_scores) остаётся как есть.
    pending = state.get('pending', [])
    sources = state.setdefault('sources', {})
    hours = state.setdefault('hours', {})
    dow_hours = state.setdefault('dow_hours', {})
    formats = state.setdefault('formats', {})
    variants = state.setdefault('variants', {})
    still_pending = []
    for post in pending:
        ts = post.get('ts', 0)
        age = now - ts
        head = post.get('head', '')
        metrics = _metrics_for(head, metrics_by_head) if age >= maturation_seconds else None
        if metrics is not None:
            reward = reward_for(metrics, weights)
            _update_avg(sources, post.get('source', ''), reward, alpha)
            _update_avg(hours, _hour_of(ts), reward, alpha)
            _update_avg(dow_hours, _dow_hour_of(ts), reward, alpha)
            _update_avg(formats, 'video' if post.get('is_video') else 'photo', reward, alpha)
            if log_variants and post.get('hashtag_n') is not None:
                _update_avg(variants, 'tags:' + _bucket_hashtags(post['hashtag_n']), reward, alpha)
        elif age < max_age_seconds:
            still_pending.append(post)
    state['pending'] = still_pending
    return state


def _metrics_for(head, metrics_by_head):
    # Same prefix-match contract as _reach_for, but returns the full metrics dict.
    if not head:
        return None
    if head in metrics_by_head:
        return metrics_by_head[head]
    for key, metrics in metrics_by_head.items():
        if key.startswith(head):
            return metrics
    return None


def _reach_for(head, reach_by_head):
    # Match the publish head to a reach key. In caption mode the IG caption is the
    # publish text PLUS appended hashtags, so for a short post the read-back head is
    # `head + " #tags"` — i.e. the reach key STARTS WITH the publish head. Require
    # exactly that prefix relationship (not loose 0.7 similarity) so distinct
    # templated headlines don't steal each other's reach.
    if not head:
        return None
    if head in reach_by_head:
        return reach_by_head[head]
    for key, reach in reach_by_head.items():
        if key.startswith(head):
            return reach
    return None


def _hour_of(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).hour


def _dow_hour_of(ts):
    # 'wday-hour' UTC, wday 0=Mon..6=Sun (matches datetime.weekday() / time.tm_wday).
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.weekday()}-{dt.hour}"


def _update_avg(bucket, key, reach, alpha):
    if key is None or key == '':
        return
    key = str(key)  # JSON object keys are strings (hours stored as '0'..'23')
    reach = float(reach)
    entry = bucket.get(key)
    if not entry:
        bucket[key] = {'reach_avg': reach, 'n': 1}
    else:
        entry['reach_avg'] = alpha * reach + (1 - alpha) * entry['reach_avg']
        entry['n'] = entry.get('n', 0) + 1


def _tier_budget(scores, current_key, base_cap, min_samples):
    # Per-run post budget: tier the current bucket against its well-sampled peers —
    # top third => full cap, middle => ~half, bottom => 1 (never 0, so the backlog
    # drains and every slot keeps sampling). Too little data, or an under-sampled
    # current bucket => full cap (explore). String keys (no int()), so it works for
    # both hour ('14') and dow-hour ('2-14') buckets.
    current_key = str(current_key)
    scored = {k: v['reach_avg'] for k, v in scores.items() if v.get('n', 0) >= min_samples}
    if len(scored) < 3 or current_key not in scored:
        return base_cap
    avgs = sorted(scored.values())
    low = avgs[len(avgs) // 3]
    high = avgs[(2 * len(avgs)) // 3]
    current = scored[current_key]
    if current >= high:
        return base_cap
    if current >= low:
        return max(1, (base_cap + 1) // 2)
    return 1


def hour_budget(hours_scores, current_hour, base_cap, min_samples, dow_hours=None, current_dow=None):
    # Per-run post budget for the current time slot, from learned reach/reward.
    # Partial pooling: prefer the fine (day-of-week × hour) bucket when it is itself
    # well-sampled, otherwise fall back to the coarse hour-only bucket. dow-hour
    # multiplies the slot space ~7x, so on a low-volume bot most dow-hour cells stay
    # thin and we correctly back off to hour-only instead of overfitting to n=1.
    if dow_hours is not None and current_dow is not None:
        dow_key = f"{current_dow}-{current_hour}"
        entry = dow_hours.get(dow_key)
        if entry and entry.get('n', 0) >= min_samples:
            return _tier_budget(dow_hours, dow_key, base_cap, min_samples)
    return _tier_budget(hours_scores, current_hour, base_cap, min_samples)


def order_sources(source_names, source_scores, default_prior, ucb_c=0.0):
    # Highest learned reward first; never-scored sources get default_prior (inf =>
    # explored first). Stable sort keeps the original order among equals.
    # ucb_c>0 adds a UCB exploration bonus c*mean_reward*sqrt(ln(total_n)/n) so
    # thin-but-promising sources keep getting sampled; ucb_c=0 => pure greedy sort
    # (unchanged default). Bonus is scaled by mean reward so it isn't swamped by the
    # raw reward magnitude.
    scored = [(name, e) for name, e in source_scores.items() if e.get('n', 0) > 0]
    total_n = sum(e['n'] for _, e in scored)
    mean_reward = (sum(e['reach_avg'] for _, e in scored) / len(scored)) if scored else 0.0

    def score(name):
        entry = source_scores.get(name)
        if entry and entry.get('n', 0) > 0:
            base = entry['reach_avg']
            if ucb_c and total_n > 0:
                base += ucb_c * mean_reward * math.sqrt(math.log(total_n) / entry['n'])
            return base
        return default_prior

    return sorted(source_names, key=score, reverse=True)


def well_sampled_sources(source_scores, min_samples):
    # Сколько источников уже хорошо просэмплированы — порог, ниже которого биас
    # источников не включаем (иначе при тонких данных нижние источники голодают).
    return sum(1 for e in source_scores.values() if e.get('n', 0) >= min_samples)


def top_sources(source_scores, limit=10):
    scored = [
        (name, entry['reach_avg'], entry.get('n', 0))
        for name, entry in source_scores.items()
        if entry.get('n', 0) > 0
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]
