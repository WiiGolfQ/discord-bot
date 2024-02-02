from discord.ext import commands

import requests
import os

from config import API_URL

class WGQBot(commands.Bot):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.games = requests.get(API_URL + "/game").json()
        self.active_matches = []
        
    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord')

bot = WGQBot()

cogs_list = [
    "cogs.queue",
    "cogs.match",
    "cogs.user_settings",
]

for cog in cogs_list:
    bot.load_extension(cog)

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)