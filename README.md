## About

#### Bot for parsing news, translating into Portuguese and publishing on a Facebook page and Instagram
- [facebook.com/desportportugal](https://www.facebook.com/desportportugal)


## Monetization (Facebook Content Monetization)

Facebook платит за КВАЛИФИЦИРОВАННЫЕ просмотры и вовлечённость на reels, длинных
видео, сторис, фото и текстовых постах. Два факта определяют архитектуру бота:

1. **Перепост чужого контента не монетизируется.** «Aggregating content» и
   «duplicative content» — прямые нарушения Content Monetization Policies:
   монетизацию снимают, а охват режут всей странице, а не только посту. Поэтому
   каждая фото-новость превращается в narrated-Reel (`REEL_RENDER_ENABLED`):
   своя плашка + своя TTS-озвучка = оригинал по построению.
2. **Длинное видео платит в 10-50 раз больше за просмотр**, чем reels
   ($1-5 против $0.02-0.20 за 1000). Отсюда режим дайджеста.

| Режим | Команда | Что делает |
|---|---|---|
| посты | `python main.py` | обычные публикации (каждые 2ч) |
| дайджест | `python main.py --mode digest` | один длинный озвученный ролик из топ-N новостей дня |

Проверить, далеко ли до порога допуска в программу:

    FACEBOOK_ACCESS_TOKEN=... python tools/monetization_check.py

Прогресс к порогу (подписчики + минуты просмотра за 60 дней) и заработок за 28
дней также попадают в суточный insights-дайджест в debug-чат.

Обучение идёт на деньгах: `LEARNING_W_WATCH_TOTAL` (минуты просмотра — валюта
порога допуска) и `LEARNING_W_EARNINGS` (`content_monetization_earnings`,
Graph v23+). Пока страница не монетизирована, денежный член равен нулю и
поведение деградирует к прежнему — без ошибок.

## Хранилище состояния (Redis)

Раньше «что уже опубликовано» бот вычитывал прямо из своих же каналов: на старте
каждого прогона тянулись последние 1000 постов из Telegram, Facebook и Instagram,
и из них собирался дедуп-леджер. Площадка была базой. Теперь база - Redis, и из
прогона чтение историй убрано полностью.

Redis обязателен. Без `REDIS_URL` (или при недоступной базе) прогон не публикует
ничего и завершается с ошибкой в debug-чат:

    REDIS_URL=rediss://default:<token>@<host>:6379

Что лежит в Redis (ключи неймспейснуты по имени конфига, `football` и `food_br`
не пересекаются):

| Ключ | Тип | Зачем |
|---|---|---|
| `botnews:<config>:published` | hash | голова поста -> площадки, куда он уже ушёл |
| `botnews:<config>:published:index` | zset | время публикации, по нему идут TTL и обрезка |
| `botnews:<config>:published:synced_at` | string | когда леджер последний раз заливали скриптом |
| `botnews:<config>:candidates` | zset | кандидаты, не добранные прошлым прогоном |

**Дедуп.** Леджер грузится из Redis, истории площадок не читаются вообще.
Сравнение голов осталось нечётким (`difflib`, порог 0.7): точечные ключи Redis его
не заменяют, иначе одна и та же новость от двух источников разошлась бы дважды.

**Очередь кандидатов.** Пул фазы 1 жил только внутри прогона: всё, на что не
хватило бюджета постов или wall-clock, терялось, и следующий прогон скрёб источники
заново. Теперь кандидат кладётся в zset (для Telegram-медиа - как `chat + message_id`,
для RSS - как URL) и восстанавливается на следующем прогоне. Опубликованные и
протухшие удаляются, остальные живут `REDIS_QUEUE_TTL_SECONDS`. В режиме дайджеста
очередь не используется.

**Пустой леджер = отказ публиковать.** Пустой леджер означает «мы ничего не
постили», и прогон переопубликовал бы всю ленту в Facebook и Instagram. Поэтому бот в такой
ситуации не публикует ничего, а пишет в debug-чат. Так же он ведёт себя, когда
Redis недоступен: лучше пропустить прогон, чем засыпать каналы дублями.

Заливается леджер отдельным скриптом - при первом запуске на новой базе и после
любой потери Redis. Это единственное место, где ещё читаются истории площадок:

    REDIS_URL=rediss://... FACEBOOK_ACCESS_TOKEN=... python tools/seed_dedup_ledger.py

Для по-настоящему нового канала, которому дубли не грозят, есть
`DEDUP_ALLOW_EMPTY_LEDGER=true`: прогон стартует с пустым леджером.

**Очередь и сбои.** Ошибка Redis посреди прогона гасит его до конца прогона:
очередь и дозапись леджера просто перестают работать, уже начатая публикация
доводится до конца.

Ручки (все через env, откат без правки кода):

| Переменная | Дефолт | Что делает |
|---|---|---|
| `REDIS_URL` | пусто | адрес Redis; без него бот не публикует |
| `REDIS_ENABLED` | `true` | общий выключатель |
| `REDIS_NAMESPACE` | `botnews` | префикс ключей |
| `REDIS_DEDUP_ENABLED` | `true` | леджер опубликованного |
| `REDIS_DEDUP_TTL_SECONDS` | 30 дней | сколько помним голову |
| `REDIS_DEDUP_MAX_HEADS` | 3000 | потолок размера леджера (объединение трёх площадок) |
| `DEDUP_ALLOW_EMPTY_LEDGER` | `false` | разрешить прогон с пустым леджером |
| `REDIS_QUEUE_ENABLED` | `true` | очередь кандидатов |
| `REDIS_QUEUE_TTL_SECONDS` | 6 часов | срок годности кандидата |
| `REDIS_QUEUE_MAX` | 200 | потолок длины очереди |

## Telegram: только источник новостей

Telegram остался в проекте одной ролью - читать чужие каналы из
`telegram_channels`. Публикации туда больше нет, свой канал и debug-чат
выпилены, бота (@PostmanPortugalBot) нет.

Почему: канал давал шесть подписчиков и ноль денег, а публикация в него
зависела от того, что бот числится в администраторах - стоило правам пропасть, и
каждый пост сжигал по пять повторных попыток впустую. Деньги живут на Facebook,
дедуп после переезда в Redis от канала не зависит.

Что из этого следует:

* Публикация идёт только в Facebook и Instagram; `Platform.TELEGRAM` в коде
  больше нет.
* Секрет `TELEGRAM_TOKEN_BOT` не используется, его можно удалить. `TELEGRAM_API_ID`,
  `TELEGRAM_API_HASH` и `TELEGRAM_SESSION` нужны по-прежнему: без них не читаются
  каналы-источники.
* Служебные сообщения (ошибки парсеров, сводка прогона, суточный дайджест
  инсайтов) уходят в `GITHUB_STEP_SUMMARY` и видны на странице прогона.
* Упавший прогон теперь делает job красным, и о падении сообщает сам GitHub.
  Раньше `continue-on-error: true` держал job зелёным, и бот мог лежать молча.

## Steps to Run the Project

1. Create a virtual environment:

   `python -m venv venv`

2.	Activate the virtual environment:

    On macOS/Linux: `source venv/bin/activate`

    On Windows: `venv\Scripts\activate`

3.	Install dependencies:

    `pip install -r requirements.txt`

4.	Create a file named secret and add your credentials to it.
5.	Run the application:

    `python main.py`
6. Run tests:

    `pytest`

## Troubleshooting

### One session files are accessed by two different IP addresses
```commandline
telethon.errors.rpcerrorlist.AuthKeyDuplicatedError: The authorization key (session file) was used under two different IP addresses 
simultaneously, and can no longer be used. Use the same session exclusively, or use different sessions 
(caused by InvokeWithLayerRequest(InitConnectionRequest(GetConfigRequest)))
```
1. Remove session files `*.session`
2. Launch the bot 
3. Enter phone, code from telegram and password

### Facebook token is outdated or damaged
```commandline
Graph returned an error: (#200) This endpoint is deprecated since the required permission publish_actions is deprecated
```

1. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select App from the top right dropdown menu
3. Select item in "Page Access Token" section from dropdown, not User Token (pages_read_engagement,	pages_manage_posts) 
4. Select needed permissions (38 items)
5. Tap on "Generate Access Token" and generated new token
6. Copy access token
7. Open [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
8. Paste copied token and press "Debug"
9. Press "Extend Access Token" and copy the generated long-lived user access token
Use copied token


### Recreate Facebook app
```commandline
error: (#200) this endpoint is deprecated since the required permission publish_actions is deprecated
```
1. Open Graph API Explorer https://developers.facebook.com/tools/explorer/ 
2. Select your MetaApp 
3. Select "User Token" 
4. Set below permissions and Create Access Token 
5. Pass FB Authentication 
6. Select "Page Token" 
7. Pass FB Authentication (select your page during Authentication) 
8. Now you will find your page name inside the token combo at the bottom! Just select it and the page token will appear above. (Do NOT click Create Access Token)

Permissions: pages_manage_cta pages_manage_instant_articles pages_show_list business_management pages_messaging pages_messaging_subscriptions page_events pages_read_engagement pages_manage_metadata pages_read_user_content pages_manage_ads pages_manage_posts pages_manage_engagement

