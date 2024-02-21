from discord.ext import commands, tasks

import requests

from config import API_URL
from utils import send_table

class Leaderboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.send_leaderboards.start()
    
    @tasks.loop(minutes=15)
    async def send_leaderboards(self):
        
        # TODO: getting the channel like this is temporary
        channel = self.bot.get_channel(1209352546557100112)
        if not channel:
            # this needs to be here for when the channel is not in the cache
            channel = await self.bot.fetch_channel(1209352546557100112)
            
        await channel.purge()
        
        for game in self.bot.games:
            
            try:
                
                res = requests.get(
                    API_URL + f"/leaderboard/{game['game_id']}"
                )
                
                if not res.ok:
                    raise Exception(res.text)
                    
                leaderboard = res.json()['results']
                
                cols = [
                    ["__**Rank**__"] + [str(item['rank']) for item in leaderboard],
                    ["__**Player**__"] + [item['player']['username'] for item in leaderboard],
                    ["__**Elo**__"] + [str(item['mu']) for item in leaderboard]
                ]
                
                await send_table(channel, f"{game['game_name']} Leaderboard", cols)
                
            except Exception as e:
                await channel.send(f"Failed to get leaderboard for {game['game_name']}: {e}")
                

def setup(bot):
    bot.add_cog(Leaderboard(bot))
            