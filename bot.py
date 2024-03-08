from discord.ext import commands

import requests
import os

from config import API_URL, DISCORD_BOT_TOKEN

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
    "cogs.leaderboard",
]

for cog in cogs_list:
    bot.load_extension(cog)

token = DISCORD_BOT_TOKEN
bot.run(token)