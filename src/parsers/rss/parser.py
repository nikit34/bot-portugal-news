import asyncio
import logging

import feedparser
import httpx

from src.files_manager import SaveFileUrl, SaveVideoUrl
from src.parsers.rss.video import extract_video_url
from src.parsers.rss.channels.com.bbc import is_valid_bbc_com_entry, parse_bbc_com
from src.parsers.rss.channels.com.guardian import is_valid_guardian_entry, parse_guardian
from src.parsers.rss.channels.pt.abola import is_valid_abola_entry, parse_abola_pt
from src.parsers.rss.channels.pt.zerozero import is_valid_zerozero_entry, parse_zerozero_pt
from src.parsers.rss.channels.pt.record import is_valid_record_entry, parse_record_pt
from src.parsers.rss.channels.pt.rtp import is_valid_rtp_entry, parse_rtp_pt
from src.parsers.rss.channels.br.ge_globo import is_valid_ge_globo_entry, parse_ge_globo
from src.parsers.rss.channels.br.trivela import is_valid_trivela_entry, parse_trivela
from src.parsers.rss.channels.br.gazeta import is_valid_gazeta_entry, parse_gazeta
from src.parsers.rss.channels.br.uol import is_valid_uol_entry, parse_uol
from src.parsers.rss.channels.br.metropoles import is_valid_metropoles_entry, parse_metropoles
from src.processor.service import serve, should_stop
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT, REPEAT_REQUESTS, MESSAGE_CHUNK_SIZE, RSS_VIDEO_ENABLED
from src.producers.telegram.telegram_api import send_message_api
from src.parsers.rss.user_agents_manager import random_user_agent_headers
from src.utils.ci import get_ci_run_url
from src.utils.notify import build_error_message


app_logger = logging.getLogger('app')
stats_logger = logging.getLogger('stats')


async def rss_wrapper(client, graph, nlp, translator, telegram_bot_token, source, rss_link, posted_d, context):
    try:
        app_logger.info(f"[RSS] Starting RSS parser for source: {source}, RSS link: {rss_link}")
        await _rss_parser(client, graph, nlp, translator, telegram_bot_token, source, rss_link, posted_d, context)
        app_logger.info(f"[RSS] RSS parser completed successfully for source: {source}, RSS link: {rss_link}")
    except Exception as e:
        app_logger.error(f"[RSS] Error in RSS parser for source: {source}, RSS link: {rss_link}", exc_info=True)
        message = build_error_message(f'ERROR: {source} rss parser is down', e, get_ci_run_url())
        app_logger.error(message, exc_info=True)
        await send_message_api(message, telegram_bot_token, context)


async def _make_request(rss_link, telegram_bot_token, context, repeat=REPEAT_REQUESTS):
    httpx_client = httpx.AsyncClient()
    try:
        for attempt in range(repeat + 1):
            app_logger.debug(f"[RSS] Making request to {rss_link} (attempt {attempt + 1}/{repeat + 1})")
            try:
                response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
                response.raise_for_status()
                app_logger.debug(f"[RSS] Request successful, status code: {response.status_code}")
                return response
            except Exception as e:
                error_message = f"[RSS] Request failed (attempt {attempt + 1}/{repeat + 1}). Error: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    error_message += f", Status code: {e.response.status_code}"
                app_logger.warning(error_message)

                if attempt < repeat:
                    await asyncio.sleep(TIMEOUT)
                else:
                    message = build_error_message(f'ERROR: {rss_link} request is down', e, get_ci_run_url())
                    app_logger.error(message, exc_info=True)
                    await send_message_api(message, telegram_bot_token, context)
    finally:
        await httpx_client.aclose()

    return None


async def _process_entry(
    entry,
    source,
    client,
    graph,
    nlp,
    translator,
    posted_d,
    context
):
    # Stop the expensive per-article scrape/serve once the post budget is filled OR
    # the per-run time budget is exhausted. Remaining fresh content is picked up next
    # run (dedup keeps it available) — this keeps "nothing fresh" runs from scraping
    # every source to the end.
    if should_stop():
        return False

    message_text = ''
    image = ''

    if 'abola.pt' in source:
        if not is_valid_abola_entry(entry):
            app_logger.debug("Entry skipped - invalid Abola entry")
            return False
        message_text, image = await parse_abola_pt(entry)
    elif 'zerozero.pt' in source:
        if not is_valid_zerozero_entry(entry):
            app_logger.debug("Entry skipped - invalid Zerozero entry")
            return False
        message_text, image = parse_zerozero_pt(entry)
    elif 'record.pt' in source:
        if not is_valid_record_entry(entry):
            app_logger.debug("Entry skipped - invalid Record entry")
            return False
        message_text, image = parse_record_pt(entry)
    elif 'rtp.pt' in source:
        if not is_valid_rtp_entry(entry):
            app_logger.debug("Entry skipped - invalid RTP entry")
            return False
        message_text, image = parse_rtp_pt(entry)
    elif 'bbc.com' in source:
        if not is_valid_bbc_com_entry(entry):
            app_logger.debug("Entry skipped - invalid BBC entry")
            return False
        message_text, image = parse_bbc_com(entry)
    elif 'theguardian.com' in source:
        if not is_valid_guardian_entry(entry):
            app_logger.debug("Entry skipped - invalid Guardian entry")
            return False
        message_text, image = parse_guardian(entry)
    elif 'ge.globo.com' in source:
        if not is_valid_ge_globo_entry(entry):
            app_logger.debug("Entry skipped - invalid ge.globo entry")
            return False
        message_text, image = parse_ge_globo(entry)
    elif 'trivela.com.br' in source:
        if not is_valid_trivela_entry(entry):
            app_logger.debug("Entry skipped - invalid Trivela entry")
            return False
        message_text, image = parse_trivela(entry)
    elif 'gazetaesportiva.com' in source:
        if not is_valid_gazeta_entry(entry):
            app_logger.debug("Entry skipped - invalid Gazeta entry")
            return False
        message_text, image = parse_gazeta(entry)
    elif 'uol.com.br' in source:
        if not is_valid_uol_entry(entry):
            app_logger.debug("Entry skipped - invalid UOL entry")
            return False
        message_text, image = parse_uol(entry)
    elif 'metropoles.com' in source:
        if not is_valid_metropoles_entry(entry):
            app_logger.debug("Entry skipped - invalid Metropoles entry")
            return False
        message_text, image = parse_metropoles(entry)

    # Если фид несёт прямое видео (mp4-enclosure / media:content medium="video"),
    # постим видео (serve уже умеет .mp4 на всех платформах); картинка не нужна.
    # Иначе — прежний путь по картинке.
    video_url = extract_video_url(entry) if RSS_VIDEO_ENABLED else ''

    if not message_text or (not image and not video_url):
        app_logger.debug(f"[RSS] Skipping entry: {'No text' if not message_text else 'No media'}")
        return False

    try:
        if video_url:
            handler_url_path = SaveVideoUrl(video_url)
            app_logger.debug(f"[RSS] Created VIDEO handler for entry: {message_text}")
        else:
            handler_url_path = SaveFileUrl(image)
            app_logger.debug(f"[RSS] Created file handler for entry: {message_text}")

        await serve(client, graph, nlp, translator, message_text, handler_url_path, posted_d, context, source=source)
        app_logger.debug(f"[RSS] Successfully processed entry: {message_text}")
        return True
    except Exception as e:
        app_logger.error(f"[RSS] Error processing entry: {message_text}", exc_info=True)
        return False

async def _process_entry_chunk(
    entry_chunk,
    source,
    client,
    graph,
    nlp,
    translator,
    posted_d,
    context
):
    skipped_count = 0
    tasks = []
    
    for entry in entry_chunk:
        task = _process_entry(entry, source, client, graph, nlp, translator, posted_d, context)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    skipped_count = sum(1 for result in results if not result)
    
    return skipped_count

async def _rss_parser(
        client,
        graph,
        nlp,
        translator,
        telegram_bot_token,
        source,
        rss_link,
        posted_d,
        context
):
    app_logger.info(f"[RSS] Starting RSS parser for {source}, RSS link: {rss_link}")
    response = await _make_request(rss_link, telegram_bot_token, context)
    if response is None:
        app_logger.error(f"[RSS] No response received for {source}, RSS link: {rss_link}; skipping")
        return
    feed = feedparser.parse(response.text)
    app_logger.debug(f"[RSS] Feed parsed successfully, found {len(feed.entries)} entries")

    limit = min(MAX_NUMBER_TAKEN_MESSAGES, len(feed.entries))
    app_logger.info(f"[RSS] Processing {limit} entries from {source}")
    
    entries = feed.entries[:limit][::-1]
    entries_chunks = [entries[i:i + MESSAGE_CHUNK_SIZE] for i in range(0, len(entries), MESSAGE_CHUNK_SIZE)]
    
    skipped_count = 0
    
    for entry_chunk in entries_chunks:
        skipped_count += await _process_entry_chunk(entry_chunk, source, client, graph, nlp, translator, posted_d, context)

    stats_logger.info(
        f"[RSS] RSS parser statistics for {source}, RSS link: {rss_link}: "
        f"Total entries: {limit}, "
        f"Processed: {limit - skipped_count}, "
        f"Skipped: {skipped_count}"
    )
