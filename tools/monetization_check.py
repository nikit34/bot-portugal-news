#!/usr/bin/env python3
"""Где мы относительно денег: разовая проверка страницы против порога допуска в
Facebook Content Monetization.

Показывает подписчиков, суммарные МИНУТЫ ПРОСМОТРА за трейлинговое окно (именно в
них Meta считает допуск), заработок за 28 дней и доступность самих денежных метрик
(content_monetization_earnings появляется только на онбордженной странице).

Ничего не публикует и не меняет — только GET-запросы к Graph API.

    FACEBOOK_ACCESS_TOKEN=... python tools/monetization_check.py
    FACEBOOK_ACCESS_TOKEN=... python tools/monetization_check.py --config food_br
"""
import os
import sys
import argparse

sys.path.insert(0, os.getcwd())

from src.properties_reader import get_secret_key                    # noqa: E402
from src.static.sources import get_config                           # noqa: E402
from src.static.settings import (                                   # noqa: E402
    GRAPH_API_VERSION,
    CMP_FOLLOWERS_TARGET,
    CMP_WATCH_MINUTES_TARGET,
    CMP_FOLLOWERS_TARGET_REELS,
    CMP_WATCH_MINUTES_TARGET_REELS,
)
from src.parsers.insights import (                                  # noqa: E402
    get_facebook_page_monetization,
    get_facebook_page_insights,
    _fetch_object_insights,
)


def _bar(done, target, width=24):
    if not target:
        return ''
    filled = min(width, int(width * (done or 0) / target))
    pct = 100.0 * (done or 0) / target
    return f"[{'#' * filled}{'.' * (width - filled)}] {pct:5.1f}%"


def _line(label, done, target, unit):
    done = done or 0
    status = 'OK' if done >= target else 'нужно ещё %s %s' % (round(target - done), unit)
    print(f"  {label:<22} {_bar(done, target)}  {round(done)}/{target} {unit} — {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='football', help='имя конфига (default: football)')
    parser.add_argument('--days', type=int, default=60, help='окно минут просмотра (default: 60)')
    args = parser.parse_args()

    token = get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN')
    if not token or 'ВСТАВЬТЕ' in token:
        print('FACEBOOK_ACCESS_TOKEN не задан (env или файл secret)')
        sys.exit(2)

    context = get_config(args.config)
    page_id = context['self_facebook_page_id']
    print(f"Graph {GRAPH_API_VERSION} · страница {page_id} · конфиг {args.config}\n")

    data = get_facebook_page_monetization(token, page_id, window_days=args.days)
    followers = data.get('followers')
    minutes = data.get('watch_minutes_60d')

    if followers is None and minutes is None:
        print('Не удалось прочитать ни подписчиков, ни время просмотра — проверьте, что')
        print('токен это PAGE-токен с правами read_insights / pages_read_engagement.')

    print('Порог допуска — reels-трек (мягкий):')
    _line('подписчики', followers, CMP_FOLLOWERS_TARGET_REELS, 'шт')
    _line(f'минуты просмотра/{args.days}д', minutes, CMP_WATCH_MINUTES_TARGET_REELS, 'мин')
    print('\nПорог допуска — полный:')
    _line('подписчики', followers, CMP_FOLLOWERS_TARGET, 'шт')
    _line(f'минуты просмотра/{args.days}д', minutes, CMP_WATCH_MINUTES_TARGET, 'мин')

    print('\nДеньги:')
    if 'earnings_28d' in data:
        print(f"  заработок за 28 дней: ${data['earnings_28d']:.2f}")
    else:
        print('  content_monetization_earnings недоступна — страница ещё НЕ онбордена')
        print('  в Content Monetization (метрика отдаётся только участникам программы).')

    stats = get_facebook_page_insights(token, page_id)
    if stats:
        print('\nСтраница за сутки:')
        for key, value in stats.items():
            print(f'  {key}: {value}')

    # Диагностика прав: что именно отвалилось — метрика или доступ.
    probe = _fetch_object_insights(token, page_id, 'insights', 'page_video_view_time', period='day')
    if not probe:
        print('\nВНИМАНИЕ: page_video_view_time не читается — без неё прогресс по минутам')
        print('просмотра посчитать нельзя. Обычно это недостающее право read_insights.')


if __name__ == '__main__':
    main()
