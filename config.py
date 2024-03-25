import os

from dotenv import load_dotenv
load_dotenv()

def get_secret(key, default):
    value = os.getenv(key, default)
    return value

DISCORD_BOT_TOKEN = get_secret("DISCORD_BOT_TOKEN", None)
API_URL = get_secret("API_URL", "http://localhost:8000/api")
QUEUE_CHANNEL_ID = int(get_secret("QUEUE_CHANNEL_ID", None))
MATCH_CHANNEL_ID = int(get_secret("MATCH_CHANNEL_ID", None))
LEADERBOARD_CHANNEL_ID = int(get_secret("LEADERBOARD_CHANNEL_ID", None))
