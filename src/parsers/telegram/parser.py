import asyncio
import logging
import os

from telethon.tl.types import MessageMediaWebPage
from src.files_manager import SaveFileTelegram
from src.processor.recipe_filter import is_recipe
from src.processor.service import serve, should_stop
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, MESSAGE_CHUNK_SIZE, MAX_VIDEO_SIZE_MB
from src.producers.telegram.telegram_api import send_message_api
from src.utils.ci import get_ci_run_url
from src.utils.notify import build_error_message

app_logger = logging.getLogger('app')
stats_logger = logging.getLogger('stats')


def _download_ext(f):
    # Расширение, которое telethon РЕАЛЬНО даст файлу при download_media — повторяем
    # логику _get_proper_filename: расширение из имени документа (DocumentAttributeFilename)
    # ПОБЕЖДАЕТ, и лишь при его отсутствии берётся mime-производное. ВАЖНО: File.ext
    # наоборот mime-первое, поэтому напрямую его использовать нельзя — иначе клип с
    # mime video/mp4, но именем 'clip.mov' помечался бы .mp4 на фазе-1, а качался бы
    # .mov (фаза-2 сочла бы его фото). Так фаза-1 и фаза-2 совпадают побайтно.
    name = getattr(f, 'name', None) or ''
    ext = os.path.splitext(name)[1]
    if not ext:
        ext = getattr(f, 'ext', '') or ''
    return ext.lower()


def _message_is_video(message):
    # Видео-ность сообщения из метаданных telethon БЕЗ скачивания. Нужно на фазе-1,
    # чтобы освободить видео от текстового гейта (ценность — клип, не подпись) и дать
    # ему бонус в ранкере. КЛЮЧЕВОЕ: ограничиваемся медиа, которое telethon сохранит
    # как .mp4 — ровно то, что phase-2 _is_video (по суффиксу .mp4) признаёт видео и
    # что публикуют FB /videos + IG Reels. Не-mp4 контейнеры (.mov/.webm/.mkv от
    # «отправить как файл») НЕ помечаем видео: пайплайн их как видео не публикует, а
    # «фото»-веткой они бы съели слот пула и NLP-гейтом фазы-2 отбросились.
    f = getattr(message, 'file', None)
    if f is None:
        return False
    mime = getattr(f, 'mime_type', '') or ''
    return mime.startswith('video/') and _download_ext(f) == '.mp4'


def _video_too_large(message):
    # Крупный клип (> MAX_VIDEO_SIZE_MB) отсекаем ДО скачивания по размеру из метаданных
    # telethon (message.file.size), а не после полной загрузки — иначе 200-МБ файл
    # качается целиком, занимает слот пула и жрёт wall-clock дренажа, чтобы затем быть
    # отброшенным. Размер неизвестен => не режем (fail-open, backstop — _large_video_size).
    size = getattr(getattr(message, 'file', None), 'size', None)
    return bool(size) and size > MAX_VIDEO_SIZE_MB * 1024 * 1024


async def telegram_wrapper(client, getter_client, graph, nlp, translator, telegram_bot_token, channel_link, posted_d, context):
    app_logger.info(f"[Telegram] Starting Telegram parser for channel: {channel_link}")
    try:
        await _telegram_parser(client, getter_client, graph, nlp, translator, channel_link, posted_d, context)
        app_logger.info(f"[Telegram] Telegram parser completed successfully for channel: {channel_link}")
    except Exception as e:
        app_logger.error(f"[Telegram] Error in Telegram parser for channel {channel_link}", exc_info=True)
        message = build_error_message(f'ERROR: {channel_link} telegram parser is down', e, get_ci_run_url())
        app_logger.error(message)
        await send_message_api(message, telegram_bot_token, context)


async def _process_message_chunk(
    message_chunk,
    client,
    getter_client,
    graph,
    nlp,
    translator,
    posted_d,
    context,
    source
):
    skipped_count = 0
    for message in message_chunk:
        # Stop once the post budget is filled or the per-run time budget is exhausted.
        if should_stop():
            break

        message_text = message.raw_text

        if not message_text or isinstance(message.media, MessageMediaWebPage) or not message.media:
            skipped_count += 1
            app_logger.debug(f"[Telegram] Skipping message: {'No text' if not message_text else 'No media'}")
            continue

        # Food-конфиг (recipe_only): в канал только рецепты. Проверяем подпись поста —
        # у кулинарных каналов рецепт обычно расписан прямо в тексте (ингредиенты/способ
        # или само слово «receita»); промо/анонсы без этих признаков отсекаем.
        if context.get('recipe_only') and not is_recipe(message_text):
            skipped_count += 1
            app_logger.debug("[Telegram] Skipping non-recipe message (recipe_only)")
            continue

        try:
            is_video_hint = _message_is_video(message)
            # Крупное видео режем ДО скачивания (по метаданным), чтобы 200-МБ клип не
            # занял слот пула и не съел wall-clock дренажа впустую.
            if is_video_hint and _video_too_large(message):
                skipped_count += 1
                app_logger.debug(f"[Telegram] Skipping oversized video (pre-download): {message_text}")
                continue

            handler_url_path = SaveFileTelegram(getter_client, message)
            app_logger.debug(
                f"[Telegram] Created file handler for message (video={is_video_hint}): {message_text}")

            await serve(client, graph, nlp, translator, message_text, handler_url_path,
                        posted_d, context, source=source, is_video_hint=is_video_hint)
            app_logger.debug(f"[Telegram] Successfully processed message: {message_text}")
        except Exception as e:
            app_logger.error(f"[Telegram] Error processing message: {message_text}", exc_info=True)
            skipped_count += 1
    
    return skipped_count


async def _telegram_parser(client, getter_client, graph, nlp, translator, channel_link, posted_d, context):
    app_logger.info(f"[Telegram] Initializing message iteration for channel: {channel_link}")
    message_count = 0
    skipped_count = 0
    current_message_chunk = []
    message_chunks = []
    
    async for message in getter_client.iter_messages(channel_link, limit=MAX_NUMBER_TAKEN_MESSAGES):
        message_count += 1
        current_message_chunk.append(message)
        
        if len(current_message_chunk) >= MESSAGE_CHUNK_SIZE:
            message_chunks.append(current_message_chunk)
            current_message_chunk = []
    
    if current_message_chunk:
        message_chunks.append(current_message_chunk)
    
    if message_chunks:
        app_logger.debug(f"[Telegram] Processing {len(message_chunks)} chunks in parallel")
        chunk_results = await asyncio.gather(*[
            _process_message_chunk(
                message_chunk, client, getter_client, graph, nlp, translator, posted_d, context, channel_link
            ) for message_chunk in message_chunks
        ])
        skipped_count = sum(chunk_results)

    name_channel = '@' + channel_link.split('/')[-1]
    stats_logger.info(
        f"[Telegram] Telegram parser statistics for channel {channel_link}, name: {name_channel}: "
        f"Total messages: {message_count}, "
        f"Processed: {message_count - skipped_count}, "
        f"Skipped: {skipped_count}"
    )
