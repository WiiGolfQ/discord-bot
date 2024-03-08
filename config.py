import os

from dotenv import load_dotenv
load_dotenv()

def get_secret(key, default):
    value = os.getenv(key, default)
    if os.path.isfile(value):
        with open(value) as f:
            return f.read()
    return value

DISCORD_BOT_SECRET = get_secret("DISCORD_BOT_SECRET", None)
API_URL = get_secret("API_URL", "http://backend:8000/api")
QUEUE_CHANNEL_ID = int(get_secret("QUEUE_CHANNEL_ID", 1199195608091725954))