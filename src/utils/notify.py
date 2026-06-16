import re

from src.static.settings import MAX_ERROR_RESPONSE_CHARS

# Graph API errors stringify to include the request URL, which carries the
# access_token as a query param; the rupload path uses an "OAuth <token>" header.
# Scrub both before anything is logged to stdout (CI logs) or sent to the chat.
_SECRET_PATTERNS = [
    (re.compile(r'(access_token=)[^&\s]+'), r'\1***'),
    (re.compile(r'(OAuth )[^\s\'"]+'), r'\1***'),
]


def redact_secrets(text):
    text = str(text)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def build_error_message(summary, error, run_url):
    """Build a Telegram-safe error notification.

    The upstream response body is truncated so the message stays under Telegram's
    sendMessage length limit (4096 chars). A full HTML error page would otherwise
    blow past that limit and the alert itself would fail with 400 Bad Request,
    never reaching the chat.
    """
    response = getattr(error, 'response', None)
    response_text = ''
    if response is not None:
        body = (getattr(response, 'text', '') or '')[:MAX_ERROR_RESPONSE_CHARS]
        if body:
            response_text = f', response: {body}'

    message = redact_secrets(f'{summary}\n{str(error)}{response_text}')
    if run_url:
        message += f'\n<a href="{run_url}">Open CI logs</a>'
    return message


def build_run_summary(stats, failures, image_summary):
    """One-glance run summary for the debug chat (what published, what silently failed)."""
    platforms = stats.get('platforms') or {}
    lines = [f"📦 Прогон: опубликовано {stats.get('posts', 0)}"]
    if platforms:
        lines.append('  ' + ', '.join(f'{name}:{count}' for name, count in sorted(platforms.items())))
    lines.append(
        f"IG за сутки: {stats.get('ig_today', 0)}/{stats.get('ig_limit', 0)} "
        f"(+{stats.get('ig_this_run', 0)} в прогоне)")
    if stats.get('meta_circuit_open'):
        lines.append('⚠️ Meta circuit open — рейт-лимит FB/IG')
    if failures.get('comment'):
        lines.append(f"⚠️ первый комментарий IG не отправлен: {failures['comment']}")
    if failures.get('story'):
        lines.append(f"⚠️ IG Stories не опубликованы: {failures['story']}")
    if failures.get('fb_story'):
        lines.append(f"⚠️ FB Stories не опубликованы: {failures['fb_story']}")
    if image_summary:
        lines.append(image_summary)
    return '\n'.join(lines)
