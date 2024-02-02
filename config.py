import os

from dotenv import load_dotenv
load_dotenv()

API_URL = os.environ.get("WGQ_API_URL")
GUILD_ID = int(os.environ.get("GUILD_ID"))
QUEUE_CHANNEL_ID = int(os.environ.get("QUEUE_CHANNEL_ID"))