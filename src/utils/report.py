import logging
import os

logger = logging.getLogger('app')


def report(text):
    """Служебное сообщение прогона: в лог и в summary страницы GitHub Actions.

    Раньше это уходило в telegram-чат ботом. Теперь единственный канал наружу -
    сам прогон CI, поэтому пишем в GITHUB_STEP_SUMMARY: сводка видна на странице
    рана, а падение job'а GitHub присылает почтой сам.
    """
    logger.info(text)
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(text + '\n\n')
    except Exception:
        logger.warning("Could not write to the run summary", exc_info=True)
