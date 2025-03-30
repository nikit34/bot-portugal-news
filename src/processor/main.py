from src.storage.redis_client import PostHistoryStorage

async def main():
    # ... existing initialization code ...
    
    logger.info("Initializing Redis storage")
    storage = PostHistoryStorage()
    
    try:
        # Заменяем очередь на Redis storage
        for channel_name, channel in telegram_channels.items():
            logger.debug(f"Adding task for Telegram channel: {channel_name}")
            task = telegram_wrapper(
                getter_client=getter_client,
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                channel=channel,
                storage=storage  # Передаем storage вместо posted_q
            )
            tasks.append(task)
            
        for source, rss_link in rss_channels.items():
            logger.debug(f"Adding task for RSS source: {source}")
            task = rss_wrapper(
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                source=source,
                rss_link=rss_link,
                storage=storage  # Передаем storage вместо posted_q
            )
            tasks.append(task)
            
        # ... rest of the existing code ... 