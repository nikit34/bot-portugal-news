import os
import asyncio
import logging
import argparse
import time

import spacy
from telethon import TelegramClient
from telethon.sessions import StringSession
from deep_translator import GoogleTranslator
import facebook as fb

from src.files_manager import clean_tmp_folder
from src.parsers.facebook.self_parser import get_facebook_published_messages
from src.parsers.instagram.self_parser import get_instagram_published_messages
from src.parsers.telegram.self_parser import get_telegram_published_messages
from src.processor.history_comparator import process_post_histories
from src.processor.image_filter import image_filter_summary
from src.parsers.rss.parser import rss_wrapper
from src.parsers.rss.channels.pt.abola import close_client as close_abola_client
from src.parsers.telegram.parser import telegram_wrapper
from src.parsers.insights import (
    report_insights, should_report_insights, get_instagram_reach_by_head,
    get_instagram_metrics_by_head, get_facebook_metrics_by_head,
)
from src.processor import learning
from src.processor.service import (
    get_publish_records, should_stop, set_run_cap,
    set_ig_daily, set_deadline, set_drain_reserve, ig_posts_this_run, get_run_stats, drain_pool,
)
from src.producers.instagram.producer import get_failure_counts
from src.producers.facebook.producer import get_failure_counts as get_facebook_failure_counts
from src.properties_reader import get_secret_key
from src.static.settings import (
    COUNT_UNIQUE_MESSAGES,
    TARGET_LANGUAGE,
    INSIGHTS_MEDIA_LIMIT,
    MAX_POSTS_PER_RUN,
    INSTAGRAM_DAILY_POST_LIMIT,
    RUN_TIME_BUDGET_SECONDS,
    RUN_SUMMARY_ENABLED,
    LEARNING_STATE_PATH,
    LEARNING_BIAS_ENABLED,
    LEARNING_DEFAULT_PRIOR,
    LEARNING_MATURATION_SECONDS,
    LEARNING_MAX_AGE_SECONDS,
    LEARNING_ALPHA,
    LEARNING_TIME_BIAS_ENABLED,
    LEARNING_HOUR_MIN_SAMPLES,
    LEARNING_DOW_HOUR_ENABLED,
    LEARNING_BANDIT_ENABLED,
    LEARNING_UCB_C,
    LEARNING_SOURCE_MIN_SAMPLES,
    LEARNING_REWARD_ENABLED,
    LEARNING_W_SHARE,
    LEARNING_W_COMMENT,
    LEARNING_W_LIKE,
    LEARNING_W_REACH,
    LEARNING_SCORE_BY_TTL_ENABLED,
    LEARNING_SCORE_TTL_SECONDS,
    FB_POST_INSIGHTS_ENABLED,
    VARIANT_LOGGING_ENABLED,
    RANKER_ENABLED,
    RANKER_DRAIN_RESERVE_SECONDS,
)
from src.static.sources import get_config
from src.producers.telegram.telegram_api import send_message_api
from src.utils.logger import setup_logging
from src.utils.ci import get_ci_run_url
from src.utils.notify import build_error_message, build_run_summary

setup_logging()
app_logger = logging.getLogger('app')

app_logger.info("Starting bot application")


def resolve_page_token(graph, page_id):
    # FACEBOOK_ACCESS_TOKEN may be a User / System-User token, whose /me is the user,
    # NOT the Page. But page posting (graph.put_photo -> me/photos lands on /me) and
    # page-post insights both require a PAGE access token. Resolve it from /me/accounts
    # for the configured page and swap it in. Best-effort: if the token is already a
    # page token (no accounts returned) or the lookup fails, keep it as-is so the run
    # still proceeds instead of crashing on startup.
    try:
        accounts = graph.get_connections('me', 'accounts', fields='id,access_token')
        for acc in accounts.get('data', []):
            if str(acc.get('id')) == str(page_id) and acc.get('access_token'):
                app_logger.info("[facebook] resolved Page access token from /me/accounts")
                return acc['access_token']
        app_logger.info("[facebook] no matching page in /me/accounts; using token as-is")
    except Exception as e:
        app_logger.warning(f"[facebook] page-token resolution failed ({e}); using token as-is")
    return graph.access_token


async def main(config_name):
    app_logger.info(f"Initializing main application with config: {config_name}")
    
    context = get_config(config_name)
    
    app_logger.debug("Loading secret keys")
    telegram_api_id = get_secret_key('.', 'TELEGRAM_API_ID')
    telegram_api_hash = get_secret_key('.', 'TELEGRAM_API_HASH')
    telegram_bot_token = get_secret_key('.', 'TELEGRAM_TOKEN_BOT')
    facebook_access_token = get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN')
    app_logger.debug("Secret keys loaded successfully")

    app_logger.info("Initializing Telegram clients")
    client = TelegramClient('bot', telegram_api_id, telegram_api_hash)
    # User-account session: prefer the TELEGRAM_SESSION secret (StringSession) so the
    # credential lives in CI secrets, not in a committed .session file; fall back to
    # the local 'getter_bot' file session for local development.
    telegram_session = os.environ.get('TELEGRAM_SESSION')
    getter_session = StringSession(telegram_session) if telegram_session else 'getter_bot'
    getter_client = TelegramClient(getter_session, telegram_api_id, telegram_api_hash)
    app_logger.debug("Telegram clients created")

    app_logger.info("Initializing Facebook Graph API")
    graph = fb.GraphAPI(access_token=facebook_access_token)
    graph.access_token = resolve_page_token(graph, context['self_facebook_page_id'])
    app_logger.debug("Facebook Graph API initialized")

    app_logger.info("Loading NLP model and translator")
    nlp = spacy.load('pt_core_news_sm')
    translator = GoogleTranslator(source='auto', target=TARGET_LANGUAGE)
    app_logger.debug("NLP model and translator loaded successfully")

    app_logger.info("Starting Telegram clients")
    tasks = [
        client.start(bot_token=telegram_bot_token),
        getter_client.start()
    ]
    await asyncio.gather(*tasks)
    app_logger.info("Telegram clients started successfully")

    try:
        # Per-run wall-clock budget so "nothing fresh" runs don't scrape every source
        # to the very end and trip the CI timeout (item 12).
        set_deadline(time.monotonic() + RUN_TIME_BUDGET_SECONDS)
        # With the ranker on, reserve wall-clock for phase-2 drain so a content-rich
        # run can't spend the whole budget pooling and then publish nothing.
        if RANKER_ENABLED:
            set_drain_reserve(RANKER_DRAIN_RESERVE_SECONDS)
        today = time.strftime('%Y-%m-%d', time.gmtime())

        app_logger.info("Fetching message history from Facebook, Instagram and Telegram")
        # Fetch the three histories concurrently so adding Instagram doesn't extend
        # startup: FB/IG are blocking `requests` calls (offloaded to threads), TG is async.
        facebook_history, instagram_history, telegram_history = await asyncio.gather(
            asyncio.to_thread(get_facebook_published_messages, graph, context, COUNT_UNIQUE_MESSAGES),
            asyncio.to_thread(get_instagram_published_messages, graph, context, COUNT_UNIQUE_MESSAGES),
            get_telegram_published_messages(getter_client, COUNT_UNIQUE_MESSAGES, context),
        )
        app_logger.info(
            f"Loaded history — Facebook: {len(facebook_history)}, "
            f"Instagram: {len(instagram_history)}, Telegram: {len(telegram_history)}")

        posted_d = process_post_histories(facebook_history, telegram_history, instagram_history)
        app_logger.info(f"Dedup history: {len(posted_d)} unique heads")

        state = learning.load_state(LEARNING_STATE_PATH)

        # Seed today's Instagram post count so serve stops publishing to IG before
        # tripping Meta's daily limit (item 9).
        set_ig_daily(learning.ig_posts_today(state, today), INSTAGRAM_DAILY_POST_LIMIT)

        if LEARNING_TIME_BIAS_ENABLED:
            gm = time.gmtime()
            current_hour = gm.tm_hour
            cap = learning.hour_budget(
                state['hours'], current_hour, MAX_POSTS_PER_RUN, LEARNING_HOUR_MIN_SAMPLES,
                dow_hours=state.get('dow_hours', {}) if LEARNING_DOW_HOUR_ENABLED else None,
                current_dow=gm.tm_wday if LEARNING_DOW_HOUR_ENABLED else None)
            set_run_cap(cap)
            app_logger.info(
                f"Time bias ON — dow {gm.tm_wday} hour {current_hour:02d} UTC "
                f"=> post budget {cap}/{MAX_POSTS_PER_RUN}")

        app_logger.info("Preparing parsing tasks")
        # (source_name, factory): lazy coroutines so the learning bias can run
        # sources in score order and stop once the per-run budget is filled,
        # skipping the fetch of the remaining lower-ranked sources.
        source_jobs = []

        for channel_link in context['telegram_channels']:
            source_jobs.append((channel_link, lambda channel_link=channel_link: telegram_wrapper(
                client=client, getter_client=getter_client, graph=graph, nlp=nlp,
                translator=translator, telegram_bot_token=telegram_bot_token,
                channel_link=channel_link, posted_d=posted_d, context=context)))

        for source, rss_link in context['rss_channels'].items():
            source_jobs.append((source, lambda source=source, rss_link=rss_link: rss_wrapper(
                client=client, graph=graph, nlp=nlp, translator=translator,
                telegram_bot_token=telegram_bot_token, source=source, rss_link=rss_link,
                posted_d=posted_d, context=context)))

        # Source bias only kicks in once enough sources are well-sampled — otherwise
        # the sequential stop-on-budget loop would starve thin-but-unscored sources.
        bias_ready = (
            LEARNING_BIAS_ENABLED
            and learning.well_sampled_sources(state['sources'], LEARNING_SOURCE_MIN_SAMPLES)
            >= LEARNING_SOURCE_MIN_SAMPLES)
        if LEARNING_BIAS_ENABLED and not bias_ready:
            app_logger.info(
                "Learning bias requested but too few well-sampled sources; "
                "running all sources in parallel (explore)")
        if bias_ready:
            ucb_c = LEARNING_UCB_C if LEARNING_BANDIT_ENABLED else 0.0
            ordered = learning.order_sources(
                [name for name, _ in source_jobs], state['sources'], LEARNING_DEFAULT_PRIOR, ucb_c)
            rank = {name: i for i, name in enumerate(ordered)}
            source_jobs.sort(key=lambda job: rank[job[0]])
            app_logger.info(
                f"Learning bias ON (ucb_c={ucb_c}) — processing sources by reward: {ordered}")
            for name, factory in source_jobs:
                if should_stop():
                    app_logger.info("Post or time budget exhausted; skipping remaining lower-ranked sources")
                    break
                await factory()
        else:
            app_logger.info(f"Starting {len(source_jobs)} parsing tasks")
            await asyncio.gather(*[factory() for _, factory in source_jobs])

        app_logger.info("All parsing tasks completed successfully")

        # Candidate ranker phase 2: publish the best-scoring pooled candidates.
        if RANKER_ENABLED:
            await drain_pool(client, graph, nlp, state)

        app_logger.info(image_filter_summary())

        # Attribute this run's publishes to their sources for the learning loop.
        # Carry the captured publish IDs + features so later scoring can attribute
        # FB post metrics precisely (by id) and learn format/hashtag variants.
        for record in get_publish_records():
            learning.record_publish(
                state, record['head'], record['source'], record['ts'],
                fb_id=record.get('fb_id'), ig_id=record.get('ig_id'),
                is_video=record.get('is_video'), hashtag_n=record.get('hashtag_n'))

        # Persist today's Instagram post count for the daily quota (item 9).
        learning.add_ig_posts(state, today, ig_posts_this_run())

        now = time.time()
        send_digest = should_report_insights()
        # Score on matured outcomes either at the daily digest hour or, when enabled,
        # on any run past the scoring TTL (so a missed/failed digest run doesn't lose
        # freshness). The digest itself still goes out only at INSIGHTS_REPORT_HOUR.
        score_now = send_digest or (
            LEARNING_SCORE_BY_TTL_ENABLED
            and (now - state.get('last_scored_ts', 0)) > LEARNING_SCORE_TTL_SECONDS)

        if score_now:
            if LEARNING_REWARD_ENABLED:
                app_logger.info("Scoring on matured engagement-weighted reward")
                # Facebook is the PRIMARY reward signal — the page is the audience we
                # actually grow. FB engagement (shares/comments/reactions) is attributed
                # by exact fb_id for every matured pending post, so it anchors the scored
                # set. Instagram only SUPPLEMENTS reach: FB reports no post-level reach in
                # Graph v18 (post_impressions_unique → #100), so reach is the single
                # metric we still source from IG. IG also backfills engagement only for
                # posts FB couldn't report (e.g. FB publish failed), so no post is lost.
                metrics_by_head = {}
                if FB_POST_INSIGHTS_ENABLED:
                    metrics_by_head = await asyncio.to_thread(
                        get_facebook_metrics_by_head, graph.access_token,
                        state.get('pending', []), now, LEARNING_MATURATION_SECONDS)
                ig_metrics = await asyncio.to_thread(
                    get_instagram_metrics_by_head, graph.access_token,
                    context['self_instagram_channel'], INSIGHTS_MEDIA_LIMIT,
                    LEARNING_MATURATION_SECONDS, now)
                for head, m in ig_metrics.items():
                    entry = metrics_by_head.setdefault(head, {})
                    entry['reach'] = m.get('reach')                 # IG owns reach
                    entry.setdefault('likes', m.get('likes'))       # FB wins if present
                    entry.setdefault('comments', m.get('comments'))
                weights = {'share': LEARNING_W_SHARE, 'comment': LEARNING_W_COMMENT,
                           'like': LEARNING_W_LIKE, 'reach': LEARNING_W_REACH}
                learning.update_scores_metrics(
                    state, metrics_by_head, weights, now,
                    LEARNING_MATURATION_SECONDS, LEARNING_MAX_AGE_SECONDS, LEARNING_ALPHA,
                    log_variants=VARIANT_LOGGING_ENABLED)
            else:
                app_logger.info("Scoring sources on matured reach")
                reach_by_head = await asyncio.to_thread(
                    get_instagram_reach_by_head, graph.access_token, context['self_instagram_channel'],
                    INSIGHTS_MEDIA_LIMIT, LEARNING_MATURATION_SECONDS, now)
                learning.update_scores(
                    state, reach_by_head, now,
                    LEARNING_MATURATION_SECONDS, LEARNING_MAX_AGE_SECONDS, LEARNING_ALPHA)
            state['last_scored_ts'] = now

        if send_digest:
            await report_insights(
                graph, telegram_bot_token, context,
                source_ranking=learning.top_sources(state['sources']),
                hour_ranking=learning.top_sources(state['hours']),
                dow_hour_ranking=learning.top_sources(state.get('dow_hours', {})),
                format_ranking=learning.top_sources(state.get('formats', {})),
                variant_ranking=learning.top_sources(state.get('variants', {})))

        learning.save_state(LEARNING_STATE_PATH, state)

        # Surface what happened this run (and any silent best-effort degradations:
        # failed first comments / Stories) to the debug chat — only when noteworthy.
        if RUN_SUMMARY_ENABLED:
            stats = get_run_stats()
            failures = {**get_failure_counts(), **get_facebook_failure_counts()}
            if stats['posts'] or any(failures.values()) or stats['meta_circuit_open']:
                summary = build_run_summary(stats, failures, image_filter_summary())
                await send_message_api(summary, telegram_bot_token, context)
    except Exception as e:
        app_logger.error("Critical error occurred during execution", exc_info=True)
        message = build_error_message('ERROR: Parsers is down', e, get_ci_run_url())
        app_logger.error(message)
        await send_message_api(message, telegram_bot_token, context)
    finally:
        app_logger.info("Cleaning up temporary files")
        clean_tmp_folder()
        try:
            await close_abola_client()
        except Exception:
            app_logger.warning("Error closing abola HTTP client", exc_info=True)
        app_logger.info("Cleanup completed")
        for tg_client in (client, getter_client):
            try:
                await tg_client.disconnect()
            except Exception:
                app_logger.warning("Error disconnecting Telegram client", exc_info=True)
        app_logger.info("Telegram clients disconnected")


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Bot for collecting and posting news')
        parser.add_argument('--config', type=str, default='football',
                          help='Configuration name under src/static/configs (default: football)')
        args = parser.parse_args()

        app_logger.info("Starting application")
        asyncio.run(main(args.config))
        app_logger.info("Application completed successfully")
    except KeyboardInterrupt:
        app_logger.info("Application interrupted by user")
    except Exception as e:
        app_logger.critical("Application crashed", exc_info=True)
