import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger('app')


def _empty_state():
    return {'version': 1, 'pending': [], 'sources': {}, 'hours': {}}


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
        return state
    except (FileNotFoundError, ValueError, OSError) as e:
        logger.info(f"[learning] no usable state at {path} ({e}); starting fresh")
        return _empty_state()


def save_state(path, state):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write-then-rename so a crash/timeout mid-write can't leave a half JSON file.
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def record_publish(state, head, source, ts):
    # Remember which source produced a just-published post so its reach can be
    # attributed back to that source once it matures (hours/days later, another run).
    if not head or not source:
        return
    state.setdefault('pending', []).append({'head': head, 'source': source, 'ts': ts})


def update_scores(state, reach_by_head, now, maturation_seconds, max_age_seconds, alpha):
    # Attribute matured reach to BOTH its source and its publish hour (EW-average),
    # drop scored/expired posts.
    pending = state.get('pending', [])
    sources = state.setdefault('sources', {})
    hours = state.setdefault('hours', {})
    still_pending = []
    for post in pending:
        ts = post.get('ts', 0)
        age = now - ts
        head = post.get('head', '')
        if age >= maturation_seconds and head in reach_by_head:
            reach = reach_by_head[head]
            _update_avg(sources, post.get('source', ''), reach, alpha)
            _update_avg(hours, _hour_of(ts), reach, alpha)
        elif age < max_age_seconds:
            still_pending.append(post)
        # else: matured but never matched within max_age → prune (can't attribute)
    state['pending'] = still_pending
    return state


def _hour_of(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).hour


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


def hour_budget(hours_scores, current_hour, base_cap, min_samples):
    # Per-run post budget for the current UTC hour, from learned reach. Tiers the
    # hour against well-sampled peers: top third => full cap, middle => ~half,
    # bottom => 1 (never 0, so the backlog drains and every hour keeps sampling).
    # Too little data, or an under-sampled current hour => full cap (explore).
    scored = {int(h): v['reach_avg'] for h, v in hours_scores.items() if v.get('n', 0) >= min_samples}
    if len(scored) < 3 or current_hour not in scored:
        return base_cap
    avgs = sorted(scored.values())
    low = avgs[len(avgs) // 3]
    high = avgs[(2 * len(avgs)) // 3]
    current = scored[current_hour]
    if current >= high:
        return base_cap
    if current >= low:
        return max(1, (base_cap + 1) // 2)
    return 1


def order_sources(source_names, source_scores, default_prior):
    # Highest learned reach first; never-scored sources get default_prior (inf =>
    # explored first). Stable sort keeps the original order among equals.
    def score(name):
        entry = source_scores.get(name)
        if entry and entry.get('n', 0) > 0:
            return entry['reach_avg']
        return default_prior

    return sorted(source_names, key=score, reverse=True)


def top_sources(source_scores, limit=10):
    scored = [
        (name, entry['reach_avg'], entry.get('n', 0))
        for name, entry in source_scores.items()
        if entry.get('n', 0) > 0
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]
