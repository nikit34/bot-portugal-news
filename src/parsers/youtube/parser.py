import asyncio
import calendar
import logging
import time

import feedparser
import httpx

from src.files_manager import SaveYouTubeVideo, VideoSkip
from src.processor.service import serve, should_stop
from src.static.settings import (
    YOUTUBE_MAX_ITEMS_PER_CHANNEL,
    YOUTUBE_MAX_AGE_DAYS,
    REPEAT_REQUESTS,
    TIMEOUT,
)
from src.parsers.rss.user_agents_manager import random_user_agent_headers
from src.producers.telegram.telegram_api import send_message_api
from src.utils.ci import get_ci_run_url
from src.utils.notify import build_error_message

app_logger = logging.getLogger('app')
stats_logger = logging.getLogger('stats')

# Публичный RSS канала YouTube: отдаёт последние ~15 загрузок (title/link/videoid/
# дата) без ключа и без бот-проверки. Само ВИДЕО потом тянем yt-dlp по link.
_FEED_URL = 'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'


async def youtube_wrapper(client, graph, nlp, translator, telegram_bot_token,
                          source, channel_id, posted_d, context):
    app_logger.info(f"[YouTube] Starting parser for {source} (channel_id={channel_id})")
    try:
        await _youtube_parser(client, graph, nlp, translator, source, channel_id, posted_d, context)
        app_logger.info(f"[YouTube] Parser completed for {source}")
    except Exception as e:
        app_logger.error(f"[YouTube] Error in parser for {source}", exc_info=True)
        message = build_error_message(f'ERROR: {source} youtube parser is down', e, get_ci_run_url())
        await send_message_api(message, telegram_bot_token, context)


async def _fetch_feed(channel_id):
    url = _FEED_URL.format(channel_id=channel_id)
    async with httpx.AsyncClient() as http:
        for attempt in range(REPEAT_REQUESTS + 1):
            try:
                response = await http.get(url, headers=random_user_agent_headers())
                response.raise_for_status()
                return response.content
            except Exception as e:
                app_logger.warning(
                    f"[YouTube] feed request failed for {channel_id} "
                    f"(attempt {attempt + 1}/{REPEAT_REQUESTS + 1}): {e}")
                if attempt < REPEAT_REQUESTS:
                    await asyncio.sleep(TIMEOUT)
    return None


def _too_old(entry, now):
    published = entry.get('published_parsed')
    if not published:
        return False  # нет даты — не отбраковываем по возрасту
    age_days = (now - calendar.timegm(published)) / 86400.0
    return age_days > YOUTUBE_MAX_AGE_DAYS


async def _youtube_parser(client, graph, nlp, translator, source, channel_id, posted_d, context):
    content = await _fetch_feed(channel_id)
    if content is None:
        app_logger.error(f"[YouTube] No feed for {source}; skipping")
        return

    feed = feedparser.parse(content)
    now = time.time()
    # entries новейшие первыми; берём верхние N, постим в хронологии (старые раньше)
    entries = feed.entries[:YOUTUBE_MAX_ITEMS_PER_CHANNEL][::-1]
    app_logger.info(f"[YouTube] {source}: {len(entries)} candidate entries")

    processed = 0
    for entry in entries:
        if should_stop():
            break

        link = entry.get('link')
        title = entry.get('title', '')
        if not link or not title:
            continue
        if _too_old(entry, now):
            app_logger.debug(f"[YouTube] skip (too old): {title}")
            continue

        try:
            handler_url_path = SaveYouTubeVideo(link)
            await serve(client, graph, nlp, translator, title, handler_url_path,
                        posted_d, context, source=source)
            processed += 1
        except VideoSkip as e:
            app_logger.debug(f"[YouTube] skip: {e}")
        except Exception:
            app_logger.error(f"[YouTube] Error processing {link}", exc_info=True)

    stats_logger.info(
        f"[YouTube] parser stats for {source}: candidates={len(entries)}, processed={processed}")
