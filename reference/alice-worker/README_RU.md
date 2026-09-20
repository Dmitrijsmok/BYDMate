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

`agent.query` сохранён только как автомобильный fallback. Для встроенного BYDMate Agent восстановлен TTS prewarm, чтобы внешний LLM и локальный синтез прогревались параллельно.

## Карточки Alice

По умолчанию `ALICE_SMART_HOME_CARDS=compact`: в Yandex Smart Home публикуется только диагностическая карточка заряда батареи. Основной автомобильный UI остаётся в BYDMate.

Допустимые режимы:

- `compact` - одна карточка батареи;
- `legacy` / `full` - старый полный набор Smart Home карточек;
- `none` / `off` / `dialogs` - не публиковать карточки.

Это позволяет постепенно заменить штатные BYDMate карточки нашими улучшенными компонентами, не дублируя их в Alice.

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
- `ALICE_SMART_HOME_CARDS` - режим карточек, по умолчанию `compact`.

Проверка:

```bash
curl https://alice.example.com/health
```

В BYDMate указать:

- Endpoint URL: `https://alice.example.com`
- API Key: значение `BYDMATE_API_KEY` из `.env`

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
