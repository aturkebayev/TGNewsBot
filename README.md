# TGNewsBot

A production-ready Telegram bot that delivers verified world news in Russian.
No paid APIs required — only a Telegram Bot Token.

**Repository:** https://github.com/aturkebayev/TGNewsBot.git

## Features

- Fetches news from 5 trusted RSS sources (BBC, Guardian, Al Jazeera, NPR, DW)
- Translates headlines and summaries to Russian (Google Translate, free)
- Categorizes: Politics, Tech, Sport, Economy, Science
- **Breaking news** push alerts — sends immediately when importance ≥ threshold
- **6-hour important news check** — top unread articles every 6 h
- **Daily digest** at user-chosen time (09:00 / 14:00 / 19:00 MSK)
- Per-user topic subscriptions + configurable alert threshold
- Deduplication — each article shown only once per user

## Prerequisites

- Python 3.11+ — https://www.python.org/downloads/
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Git — https://git-scm.com/download/win
- (optional) Docker Desktop — https://www.docker.com/products/docker-desktop/

## Quick start (PowerShell, Windows 11)

```powershell
git clone https://github.com/aturkebayev/TGNewsBot.git
cd TGNewsBot

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env          # вставь TELEGRAM_BOT_TOKEN=<твой токен>

python main.py
```

> **Если `Activate.ps1` блокируется политикой выполнения:**
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

## Docker (PowerShell)

```powershell
Copy-Item .env.example .env
notepad .env          # вставь TELEGRAM_BOT_TOKEN=<твой токен>

docker-compose up -d
docker-compose logs -f   # просмотр логов
docker-compose down      # остановка
```

## ☁️ Бесплатный хостинг — Fly.io

Fly.io даёт 3 бесплатных VM навсегда + persistent volume для SQLite.

### Установка flyctl (PowerShell)

```powershell
# Способ 1 — winget
winget install -e --id Fly.flyctl

# Способ 2 — PowerShell скрипт
iwr https://fly.io/install.ps1 -useb | iex
```

### Деплой (один раз)

```powershell
# Зарегистрироваться / войти
fly auth signup    # или: fly auth login

# Создать приложение и volume
fly launch --name tgnewsbot --region ams --no-deploy
fly volumes create tgnewsbot_data --region ams --size 1

# Добавить токен как секрет (он НЕ попадёт в репозиторий)
fly secrets set TELEGRAM_BOT_TOKEN=<твой_токен>

# Задеплоить
fly deploy
```

### Обновление после изменений

```powershell
fly deploy
```

### Полезные команды

```powershell
fly status          # статус VM
fly logs            # live логи
fly ssh console     # SSH в контейнер
fly volumes list    # список volumes
```

> **Почему Fly.io, а не Render/Railway?**
> - Render засыпает бесплатные воркеры — бот пропустит новости
> - Railway даёт $5/мес кредит, потом просит карту
> - Fly.io: 3 VM навсегда бесплатно, persistent volume, Docker

## Bot commands

| Кнопка / команда | Описание |
|---|---|
| 📰 Новости / `/news` | Свежий дайджест (только непрочитанные) |
| 🔄 Обновить / `/fetch` | Загрузить RSS прямо сейчас |
| 🗂 Темы / `/topics` | Выбрать категории новостей |
| ⚙️ Настройки / `/settings` | Время дайджеста + порог уведомлений |
| ❓ Помощь / `/help` | Список команд |

## Как не пропустить важные новости

| Механизм | Когда срабатывает |
|---|---|
| 🚨 Breaking push | Сразу при появлении, importance ≥ порог пользователя |
| ⏰ 6-часовой алерт | В 06:05, 12:05, 18:05, 00:05 МСК — топ-3 непрочитанных важных |
| 📋 Дайджест | Раз в сутки в выбранное время — всё непрочитанное |
| 📰 По запросу | Кнопка «Новости» — только новые статьи |

Порог уведомлений настраивается в ⚙️ Настройки:
- `7+` — все заметные новости
- `8+` — важные (по умолчанию)
- `9+` — только срочные
- Отключить — только дайджест

## Configuration (.env)

```
TELEGRAM_BOT_TOKEN=your_token_here
DIGEST_TIME_DEFAULT=09:00
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
DATA_DIR=.
```

## Architecture

```
TGNewsBot/
├── bot/
│   ├── handlers.py      # Command and callback handlers
│   ├── keyboards.py     # InlineKeyboard + ReplyKeyboard builders
│   └── formatter.py     # MarkdownV2 message templates
├── parser/
│   └── rss.py           # RSS fetch + HTML strip + deduplication
├── processor/
│   └── engine.py        # translate + categorize + score
├── db/
│   └── database.py      # aiosqlite schema + async queries
├── scheduler/
│   └── jobs.py          # APScheduler: poll/digest/breaking/important
├── main.py              # Entry point + graceful shutdown
├── fly.toml             # Fly.io deployment config
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## RSS Sources

| Source         | Feed URL |
|----------------|----------|
| BBC            | https://feeds.bbci.co.uk/news/world/rss.xml |
| Guardian       | https://www.theguardian.com/world/rss |
| Al Jazeera     | https://www.aljazeera.com/xml/rss/all.xml |
| NPR News       | https://feeds.npr.org/1004/rss.xml |
| Deutsche Welle | https://rss.dw.com/rdf/rss-en-all |
