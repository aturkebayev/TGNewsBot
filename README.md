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

- Python 3.11+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

## Quick start

```bash
git clone https://github.com/aturkebayev/TGNewsBot.git
cd TGNewsBot

pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in TELEGRAM_BOT_TOKEN

python main.py
```

## Docker

```bash
cp .env.example .env
# Edit .env and fill in TELEGRAM_BOT_TOKEN

docker-compose up -d
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

| Source     | Feed URL |
|------------|----------|
| Reuters    | http://feeds.reuters.com/reuters/topNews |
| BBC        | http://feeds.bbci.co.uk/news/world/rss.xml |
| AP News    | https://feeds.apnews.com/rss/apf-topnews |
| Guardian   | https://www.theguardian.com/world/rss |
| Al Jazeera | https://www.aljazeera.com/xml/rss/all.xml |
