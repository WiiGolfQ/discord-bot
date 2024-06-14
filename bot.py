import requests

from discord.ext import commands

from config import API_URL, DISCORD_BOT_TOKEN

from utils import generate_agree_list


class WGQBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.games = requests.get(API_URL + "/game/").json()
        self.active_matches = requests.get(
            API_URL + "/match", params={"active": True}
        ).json()

        for match in self.active_matches:
            match["agrees"] = generate_agree_list(match, True)

    async def on_ready(self):
        # refresh queues
        queue = self.get_cog("Queue")
        await queue.create_queues()

        print("READY")


bot = WGQBot()

cogs_list = [
    "cogs.queue",
    "cogs.match",
    "cogs.user_settings",
    "cogs.leaderboard",
    "cogs.test",
]

for cog in cogs_list:
    bot.load_extension(cog)

token = DISCORD_BOT_TOKEN
bot.run(token)
