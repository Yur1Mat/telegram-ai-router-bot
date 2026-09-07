# Запуск в Cloudflare

Нужны бесплатный аккаунт Cloudflare, Node.js 24, Git и токен от BotFather. При небольшом числе подписчиков бот укладывается в бесплатные квоты; платный тариф автоматически подключать не нужно.

1. Клонируйте репозиторий и установите Wrangler: `npm install --save-dev wrangler`.
2. Выполните `npx wrangler login` и подтвердите доступ в браузере. Для ограниченного OAuth нужны `account:read user:read workers:write workers_scripts:write d1:write`.
3. Создайте свою базу: `npx wrangler d1 create kindness-subscribers`. В `cloudflare/wrangler.jsonc` замените `account_id` и `database_id` на свои. Имя Worker при необходимости тоже замените.
4. Создайте таблицы:

```sh
npx wrangler d1 execute kindness-subscribers --remote --file cloudflare/schema.sql --config cloudflare/wrangler.jsonc
npx wrangler deploy --config cloudflare/wrangler.jsonc
npx wrangler secret put TELEGRAM_BOT_TOKEN --config cloudflare/wrangler.jsonc
npx wrangler secret put WEBHOOK_SECRET --config cloudflare/wrangler.jsonc
```

В первый секрет вставьте токен бота. Для второго сгенерируйте случайную строку из 64 символов (латинские буквы/цифры). Не добавляйте секреты в Git. Сохраните WEBHOOK_SECRET для следующего шага.

5. Подключите Telegram методом `setWebhook`: отправьте POST в `https://api.telegram.org/bot<TOKEN>/setWebhook` с JSON-полями `url` = адрес Worker + `/telegram`, `secret_token` = WEBHOOK_SECRET, `allowed_updates` = `["message"]`, `drop_pending_updates` = `false`, `max_connections` = `1`. Передавайте токен из переменной окружения, не публикуйте полный URL с токеном. Убедитесь, что ответ содержит `ok: true`, а `getWebhookInfo` показывает нужный адрес без ошибок.
6. Отключите старые процессы отправки. Чтобы включить новую рассылку, задайте в конфигурации `"vars": {"DELIVERY_ENABLED": "true"}` и повторите `deploy`. Для остановки поставьте `false` и опубликуйте снова.
7. Отправьте боту `/start`. Проверьте ответ и `/status`. Каждый новый пользователь должен нажать Start сам.

## Расписание и проверка

Cloudflare запускает проверку каждую минуту. Отправка положена только в 08:30 и 17:30 по Москве; повторный запуск проверяет журнал доставок. При временной ошибке запрос повторяется. Обрабатывается до 10 получателей за минуту; для большой аудитории нужна отдельная очередь. После подписки сообщения начинаются со следующего времени отправки.

Проверка `/health` подтверждает доступность HTTP, но не работу расписания. Для проверки реального автоматического запуска:

```sh
npx wrangler d1 execute kindness-subscribers --remote --config cloudflare/wrangler.jsonc --command "SELECT * FROM runtime; SELECT slot,status,count(*) AS total FROM deliveries GROUP BY slot,status;"
```

`last_cron` должен обновляться автоматически. Доставка подтверждается статусом `sent` в таблице deliveries. Изменения cron могут распространяться до 15 минут. Точность до секунды не гарантируется.

Если Telegram принял сообщение, а сохранение результата в D1 оборвалось, при повторной попытке возможен дубль: Telegram sendMessage не поддерживает ключ идемпотентности. При долгом сбое бот догоняет только последнее время отправки текущего московского дня, не отправляя весь пропущенный архив.

## Приватность

D1 хранит только ID чата, статус подписки, время подписки, номер последней команды и журнал доставок. Имена и текст переписки не сохраняются. Секреты находятся в Cloudflare Secrets; в открытом репозитории их нет. Не используйте экспериментальный Python-модуль `bot.cloud` для хранения подписчиков в публичном Git.

При ротации токена замените TELEGRAM_BOT_TOKEN и повторите setWebhook. Смена токена не повреждает D1. Для резервных копий используйте D1 export и храните полученный файл приватно.
