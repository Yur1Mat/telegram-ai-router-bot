# Telegram AI Router Bot

Приватный Telegram-бот, который позволяет из Telegram добавлять API-ключи и переключаться между OpenAI, Claude (Anthropic), DeepSeek и любым OpenAI-совместимым API.

## Возможности

- выбор провайдера через inline-кнопки (`/providers`);
- отдельный зашифрованный API-ключ для каждого провайдера;
- смена модели и системного промпта без перезапуска;
- история последних 20 сообщений и команда очистки;
- доступ только для разрешённых Telegram user ID;
- запуск локально или через Docker Compose;
- пользовательский HTTPS endpoint для OpenAI-совместимых сервисов.

## 1. Создайте Telegram-бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте `/newbot`, задайте имя и username.
3. Скопируйте выданный bot token.
4. Узнайте свой числовой Telegram ID через [@userinfobot](https://t.me/userinfobot).

## 2. Настройте проект

Нужны Python 3.11+ и Git.

```powershell
git clone <URL-ЭТОГО-РЕПОЗИТОРИЯ>
cd telegram-ai-router-bot
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Откройте `.env` и укажите:

- `TELEGRAM_BOT_TOKEN` — токен от BotFather;
- `ADMIN_USER_IDS` — ваш Telegram ID (несколько ID через запятую);
- `ENCRYPTION_KEY` — результат последней команды.

Не публикуйте `.env`: файл уже внесён в `.gitignore`.

## 3. Запустите

```powershell
python -m bot
```

Или через Docker:

```powershell
docker compose up -d --build
docker compose logs -f
```

## 4. Подключите AI в самом боте

```text
/setkey openai sk-...
/setkey anthropic sk-ant-...
/setkey deepseek sk-...
/providers
```

После `/providers` нажмите нужного провайдера. Модель меняется командой, например `/model gpt-5-mini`.

Для другого OpenAI-совместимого API:

```text
/providers              # выберите Custom API
/setkey custom ВАШ_КЛЮЧ
/endpoint https://example.com/v1
/model model-name
```

Затем просто отправляйте обычные сообщения. `/clear` начинает новый диалог, `/status` показывает активные настройки.

## Безопасность

- Бот отвечает только ID из `ADMIN_USER_IDS`.
- Ключи шифруются Fernet и сохраняются в `data/bot.sqlite3`.
- Команда с ключом удаляется из чата, если Telegram разрешает удаление. Всё равно используйте только личный чат.
- Потеря `ENCRYPTION_KEY` делает сохранённые API-ключи нечитаемыми.
- При смене `ENCRYPTION_KEY` удалите локальную БД и добавьте ключи заново.

OpenAI реализован через Responses API с `store: false`; Claude — через Messages API; DeepSeek и Custom — через Chat Completions-совместимый протокол.

## Проверка

```powershell
python -m unittest discover -s tests -v
```

## Лицензия

MIT

