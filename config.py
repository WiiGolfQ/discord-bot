import os

from dotenv import load_dotenv
load_dotenv()

DISCORD_BOT_SECRET = os.environ.get("DISCORD_BOT_SECRET")
API_URL = os.environ.get("WGQ_API_URL")
QUEUE_CHANNEL_ID = int(os.environ.get("QUEUE_CHANNEL_ID"))