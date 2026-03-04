# Family Bot — Majestic RP (MVP)

Discord-бот для семейной фракции: заявки на вступление, рассмотрение рекрутёрами, отчёты на повышение и Web UI для настройки.

## Что реализовано

- Подача заявки через кнопку + Modal.
- Проверка: одна активная заявка на пользователя.
- Кулдаун после отклонения (по умолчанию 24 часа, меняется в Web UI).
- Канал рассмотрения с кнопками `✅ Принять`, `❌ Отклонить`, `📞 Обзвон`.
- ЛС-уведомления заявителю по итогам рассмотрения.
- Автовыдача роли новобранца при принятии заявки.
- Подача отчёта на повышение через кнопку + Modal.
- Рассмотрение отчётов с кнопками принятия/отклонения.
- Slash-команды: `/setup`, `/ping`, `/заявки_список`, `/кулдаун_снять`.
- Отдельный Web UI для настройки каналов, ролей и полей форм.

## Стек

- Python 3.11+
- discord.py 2.x
- SQLite
- aiohttp (Web UI)

## Быстрый старт

### 1) Установка

```bash
pip install -r requirements.txt
```

### 2) Переменные окружения

Создайте `.env`:

```env
DISCORD_BOT_TOKEN=your_token_here
BOT_DB_PATH=family_bot.db

# Web UI auth (поддерживаются также ADMIN_USERNAME/ADMIN_PASSWORD)
ADMIN_PANEL_USER=admin
ADMIN_PANEL_PASS=admin

# Web UI bind (поддерживаются также WEB_ADMIN_HOST/WEB_ADMIN_PORT)
ADMIN_PANEL_HOST=0.0.0.0
ADMIN_PANEL_PORT=5000

# Вкл/выкл автозапуск web-панели вместе с ботом
ENABLE_WEB_ADMIN_PANEL=true

# Optional: enable only if privileged intents are enabled in Discord Developer Portal
ENABLE_PRIVILEGED_INTENTS=false
```

### 3) Запуск

Бот:

```bash
python bot.py
```

Web UI теперь поднимается автоматически вместе с ботом (в том же процессе).

При необходимости можно запустить только Web UI отдельно:

```bash
python admin_panel.py
```

### 4) Первичная настройка

1. Откройте `http://<ADMIN_PANEL_HOST>:<ADMIN_PANEL_PORT>` (или `WEB_ADMIN_HOST/WEB_ADMIN_PORT` в docker-compose), например `http://localhost:5000`, и войдите в Web UI.
2. Заполните ID каналов/ролей.
3. В Discord выполните `/setup` для публикации кнопок подачи.

## Замечания

- В Discord Modal одновременно доступно до 5 полей — бот использует первые 5 полей формы каждого типа.
- Все ID в Web UI указываются в формате чисел Discord Snowflake.

- Privileged intents по умолчанию отключены для стабильного запуска. Если включаете `ENABLE_PRIVILEGED_INTENTS=true`, предварительно включите соответствующие intents в Discord Developer Portal.
