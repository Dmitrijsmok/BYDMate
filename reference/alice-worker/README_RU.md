# Reference Alice Worker / VPS

Это референсная single-car реализация bridge для интеграции Яндекс Алисы с BYDMate. Она предназначена для тестирования и как пример протокола, а не как готовый multi-user backend.

## Архитектура

Alice теперь является тонким голосовым интерфейсом к существующим функциям BYDMate:

- команды автомобиля -> локальный BYDMate NLU / ActionDispatcher;
- окна и люк в процентах -> AliceApertureController;
- навигация -> существующий BYDMate navigation engine;
- запуск приложений -> динамический launcher resolver, включая альтернативные APK вроде ReVanced/RVX;
- автомобильные вопросы, которые нельзя решить локальной командой -> `agent.query`;
- запросы вне автомобильного домена не передаются BYDMate Agent.

На прямом пути не используются GigaAM, BYDMate TTS и внешний LLM. Alice уже распознала речь, поэтому Worker передаёт в BYDMate текст или структурированную semantic-команду.

`agent.query` сохранён только как автомобильный fallback: BYDMate Agent отвечает только на вопросы об автомобиле, ответ звучит голосом BYDMate.

## Разрешения в BYDMate

В BYDMate (Настройки → Умный дом) два переключателя, оба по умолчанию выключены:

- «Алиса может управлять машиной» - климат, сиденья, свет, окна и люк (включая проценты), шторка, багажник, `vehicle.command` и сырые команды старого протокола;
- «Алиса может прокладывать маршруты» - `navigation.route`, `navigation.search`, `navigation.show`.

Запуск приложений (`app.*`, в том числе навигатора без маршрута), медиа (`media.*`), проекция на приборную панель (`navigation.cluster_*`) и `agent.query` работают всегда. Отклонённая команда подтверждается с `success: false` и ошибкой `vehicle_control_disabled` или `navigation_disabled`; её видно в `/api/debug`. Агент, отвечающий на `agent.query`, связан теми же переключателями: при выключенном разрешении у него нет инструментов управления машиной или навигации.

Все записи в машину идут через ActionDispatcher BYDMate: allowlist, ограничения по скорости (с прямым чтением скорости, при неизвестной скорости - отказ), задний багажник только при известных 0 км/ч.

## Срок жизни команды

Алиса отвечает «готово» сразу после постановки команды в очередь. Чтобы машина, которая была не в сети, не выполнила её через час, команда старше 30 секунд не выдаётся: Worker помечает её `expired` (переопределяется `ALICE_COMMAND_TTL_MS`), а BYDMate сам отбрасывает команды старше 30 секунд и подтверждает их как `expired`. Возраст BYDMate берёт из `age_ms`, который Worker добавляет к каждой команде, поэтому расхождение часов машины и сервера не мешает.

## Протокол

- `GET /api/poll?wait_ms=2000` - long-poll; ответ `{"server_time": …, "commands": [{"id", "action", "value", "text", "created_at", "age_ms"}]}`.
- `POST /api/ack` - `{"ids": [...], "results": [{"id", "success", "error"}]}`. Успешные команды удаляются, неуспешные остаются в истории с причиной. Запрос только с `ids` (старый BYDMate) означает «выполнено».
- `POST /api/state` - состояние машины: заряд, окна, люк, багажник, замок, климат, вентилятор, направление обдува, температура в салоне и на улице.

BYDMate понимает и старый протокол upstream-Worker (`{"id", "command"}` с китайской командой): такая команда считается управлением машиной и идёт через те же проверки.

## Карточки Alice

По умолчанию `ALICE_SMART_HOME_CARDS=full`: Yandex Smart Home должен видеть автомобильные устройства, потому что именно Smart Home обеспечивает прямые команды без активационной фразы, например «Алиса, включи климат».

Допустимые режимы:

- `full` / `legacy` - полный набор Smart Home устройств; нужен для прямого голосового управления автомобилем;
- `compact` - только диагностическая карточка батареи; прямые Smart Home-команды автомобилю при этом недоступны;
- `none` / `off` / `dialogs` - не публиковать Smart Home устройства.

Основной автомобильный UI всё равно остаётся в BYDMate. Карточки Yandex здесь являются также декларацией устройств и их voice-capabilities, а не только визуальным интерфейсом.

## Что находится в папке

- `worker.mjs` - Yandex Dialogs router + Yandex Smart Home + BYDMate API;
- `server.mjs` - тонкий Node.js адаптер для запуска той же логики на обычном VPS;
- `d1-sqlite.mjs` - минимальный D1-compatible слой поверх SQLite;
- `.env.example` - обязательные переменные;
- `bydmate-alice.service.example` - пример systemd unit;
- `nginx.example.conf` - пример HTTPS reverse proxy.

## Быстрый запуск на VPS

Требуется Node.js 20+ и публичный HTTPS-домен.

```bash
sudo mkdir -p /opt/bydmate-alice
sudo chown "$USER":"$USER" /opt/bydmate-alice
cd /opt/bydmate-alice
# скопировать содержимое этой папки
npm install
cp .env.example .env
nano .env
npm start
```

Минимальные переменные:

- `BYDMATE_API_KEY` - ключ Android bridge;
- `YANDEX_CLIENT_ID` - OAuth client ID Yandex Smart Home;
- `ALICE_DIALOG_TOKEN` - секрет в URL Dialogs webhook;
- `ALICE_SMART_HOME_CARDS` - режим публикации Smart Home устройств, по умолчанию `full`;
- `ALICE_COMMAND_TTL_MS` - срок жизни команды в очереди, по умолчанию `30000`.

Для Cloudflare Worker те же значения задаются как переменные (Settings → Variables) и привязка D1 `DB`. Разворачивается `worker.mjs`; отдельной копии для вставки в редактор больше нет.

Проверка:

```bash
curl https://alice.example.com/health
```

В BYDMate (Настройки → Умный дом) указать:

- адрес Worker: `https://alice.example.com`
- API-ключ: значение `BYDMATE_API_KEY` из `.env`

и включить «Мост с Алисой». Управление машиной и маршруты включаются отдельными переключателями.

Webhook Yandex Dialogs:

```text
https://alice.example.com/alice/<ALICE_DIALOG_TOKEN>
```

## Примеры маршрутизации

`Алиса, построй маршрут до аэропорта`

```text
Alice STT -> Worker navigation.route -> BYDMate navigation engine -> выбранный навигатор
```

`Алиса, открой YouTube`

```text
Alice STT -> Worker app.launch -> BYDMate launcher resolver -> YouTube/ReVanced/RVX
```

`Алиса, открой окно водителя на 40 процентов`

```text
Alice STT -> window.driver.position -> AliceApertureController -> Vehicle API
```

`Алиса, почему зимой у BYD выше расход?`

```text
Alice STT -> automotive-domain gate -> agent.query -> BYDMate Agent
```

## Ручной тест без Алисы

```bash
curl -X POST https://alice.example.com/api/enqueue \
  -H 'X-Api-Key: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"action":"climate.on"}'
```

Прямой текст автомобиля:

```bash
curl -X POST https://alice.example.com/api/enqueue \
  -H 'X-Api-Key: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"action":"vehicle.command","text":"включи климат"}'
```

Навигация:

```bash
curl -X POST https://alice.example.com/api/enqueue \
  -H 'X-Api-Key: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"action":"navigation.route","text":"{\"destination\":\"Рига\",\"go\":false}"}'
```

## Production

Для публичного сервиса текущую single-car схему нужно расширить: user/car pairing, отдельные очереди и state на автомобиль, отзываемые car credentials, rate limiting и изоляция пользователей.
