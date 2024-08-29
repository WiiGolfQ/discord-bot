# WiiGolfQ/discord-bot

This repository contains WiiGolfQ's [Discord bot](https://discord.com/developers/docs/intro). Users interact with the app through the Discord bot, which uses the REST API to communicate with the [backend](https://github.com/WiiGolfQ/backend). It is written in [Pycord](https://docs.pycord.dev/en/stable/).

#### Features

- Serving as the interface for changing user settings, joining queues, submitting scores, etc.
- Using the Discord threads feature to keep match chats organized
- Enforcing requirements to livestream gameplay on YouTube

## Running locally

### Cloning and changing environment variables

```
git clone git@github.com:wiigolfq/discord-bot
cd discord-bot

cp .env.example .env
nano .env  #change environment variables, see below
```

#### Environment variables

- `DISCORD_BOT_TOKEN`
  - Token for a Discord bot in your server that has admin privileges.
- `QUEUE_CHANNEL_ID`
- `MATCH_CHANNEL_ID`
- `LEADERBOARD_CHANNEL_ID`
  - Create channels in your server for each of these, then copy their IDs by right-clicking with developer mode turned on.
  - The match channel should be a forum.
- `API_URL`
  - The REST API URL. If running the backend locally, it will be `http://localhost:8000/v1`
 
### Running

```
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python3 bot.py
```

The bot should have started up and automatically sent messages to your channels.


