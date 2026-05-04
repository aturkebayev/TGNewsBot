# TGNewsBot

A production-ready Telegram bot that delivers verified world news in Russian.
No paid APIs required — only a Telegram Bot Token.

**Repository:** https://github.com/aturkebayev/TGNewsBot.git

## Features

- Fetches news from 5 trusted RSS sources (Reuters, BBC, AP News, Guardian, Al Jazeera)
- Translates headlines and summaries to Russian (Google Translate, free tier)
- Categorizes articles: Politics, Tech, Sport, Economy, Science
- Detects breaking news and delivers instant alerts
- Daily digest at a user-chosen time (09:00 / 14:00 / 19:00 MSK)
- Per-user topic subscriptions

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

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## Bot commands

| Command     | Description                        |
|-------------|------------------------------------|
| /start      | Welcome message + topic selection  |
| /topics     | Toggle topic subscriptions         |
| /news       | Get latest digest immediately      |
| /settings   | Set daily digest time              |
| /help       | List all commands                  |

## Configuration (.env)

```
TELEGRAM_BOT_TOKEN=your_token_here
DIGEST_TIME_DEFAULT=09:00
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
```

## Architecture

```
TGNewsBot/
├── bot/
│   ├── handlers.py      # Command and callback handlers
│   ├── keyboards.py     # InlineKeyboard builders
│   └── formatter.py     # MarkdownV2 message templates
├── parser/
│   └── rss.py           # RSS fetch + deduplication
├── processor/
│   └── engine.py        # translate + categorize + score
├── db/
│   └── database.py      # aiosqlite schema + async queries
├── scheduler/
│   └── jobs.py          # APScheduler jobs
├── main.py              # Entry point + graceful shutdown
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## RSS Sources (whitelisted)

| Source         | Feed URL |
|----------------|----------|
| BBC            | https://feeds.bbci.co.uk/news/world/rss.xml |
| Guardian       | https://www.theguardian.com/world/rss |
| Al Jazeera     | https://www.aljazeera.com/xml/rss/all.xml |
| NPR News       | https://feeds.npr.org/1004/rss.xml |
| Deutsche Welle | https://rss.dw.com/rdf/rss-en-all |
