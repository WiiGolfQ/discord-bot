from dotenv import dotenv_values

env_dict = dotenv_values(".env")

DISCORD_BOT_SECRET = env_dict["DISCORD_BOT_SECRET"]
API_URL = env_dict["WGQ_API_URL"]
QUEUE_CHANNEL_ID = int(env_dict["QUEUE_CHANNEL_ID"])