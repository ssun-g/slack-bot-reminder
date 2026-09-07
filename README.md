# Slack Reaction Reminder Bot

A small Slack bot that finds the latest message with mentions in a channel and reminds anyone who hasn't reacted to it yet.

Useful for announcements where you ask people to acknowledge with an emoji reaction and want to nudge those who haven't.

## How it works

1. Scans recent messages in the target channel and picks the latest one containing a mention (`@user`, `@channel`, or `@here`).
2. Builds the list of target users. For `@channel` / `@here`, every channel member is a target.
   - The message author and bot/app users are excluded.
3. Collects users who reacted to that message. Any emoji counts.
4. Sends a reminder to users who haven't reacted:
   - A reply in the original message thread, mentioning them
   - A direct message to each user with a link to the message

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.10 or later (uv installs it automatically if missing)
- A Slack Bot Token (starts with `xoxb-`)

### Slack app permissions (Bot Token Scopes)

| Scope | Purpose |
|---|---|
| `channels:history` | Read channel messages |
| `channels:read` | List channel members |
| `reactions:read` | Read reactions on a message |
| `users:read` | Detect bot/app users |
| `chat:write` | Post thread replies and DMs |
| `im:write` | Open DM channels with users |

For private channels, also add `groups:history` and `groups:read`.
After setting the scopes, invite the bot to the target channel.

## Installation

```bash
uv sync
cp .env.example .env
```

Edit `.env` and fill in the values:

```
SLACK_BOT_TOKEN=xoxb-your-token-here
CHANNEL_ID=C0000000000
```

## Usage

```bash
uv run python bot.py
```

Each run checks the channel once and exits. To send reminders on a schedule, use cron or a similar scheduler.

```cron
# Example: run every day at 10:00
0 10 * * * cd /path/to/slack-bot-reminder && ~/.local/bin/uv run python bot.py >> reminder.log 2>&1
```

cron runs with a limited `PATH`, so use the absolute path to `uv` (check with `which uv`).

## Project layout

- `bot.py` - all bot logic
- `pyproject.toml` / `uv.lock` - dependencies and lockfile
- `.env.example` - example environment variables
- `.gitignore` - excludes `.venv`, `.env`, etc.
