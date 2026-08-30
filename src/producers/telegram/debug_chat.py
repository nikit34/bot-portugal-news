import logging


logger = logging.getLogger('app')


async def send_debug_message(text, client, context):
    """Служебное сообщение в debug-чат. Best-effort: сбой уведомления не валит прогон."""
    try:
        await client.send_message(
            entity=int(context['self_telegram_debug_chat_id']),
            message=text,
            parse_mode='html',
            link_preview=False,
        )
    except Exception as e:
        logger.warning("Debug notification failed: " + str(e))
