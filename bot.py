from discord.ext import commands

import requests
import os
import bs4

from config import API_URL, DISCORD_BOT_SECRET

class WGQBot(commands.Bot):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        res = requests.get(API_URL + "/game/")
        
        print(res.status_code)
        print(res.headers)
        
        #print JUST TEXT using bs4
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        print(soup.get_text())
        
        
        self.games = res.json()
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

token = DISCORD_BOT_SECRET
bot.run(token)