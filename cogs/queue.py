from discord.ext import commands
import discord
import datetime

import requests

from config import API_URL, QUEUE_CHANNEL_ID

class Queue(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
    
    class QueueView(discord.ui.View):
    
        def __init__(self, bot, game):
            super().__init__(timeout=None)
            
            self.bot = bot
            
            if game:
                self.game_id = game['game_id']
                self.game_name = game['game_name']
            else:
                self.game_id = 0
                self.game_name = None
        
        @discord.ui.button(emoji="⛳", style=discord.ButtonStyle.secondary)
        async def button_callback(self, button, interaction):
            
            await interaction.response.defer(ephemeral=True)
            
            # temporary code for beta test season
            time = datetime.datetime.now()
            start = datetime.datetime.fromtimestamp(1710277200)
            end = datetime.datetime.fromtimestamp(1712635200)
            if time < start or time > end: # march 12th 5:00pm est to march 26th 5:00pm est
                await interaction.followup.send(":(", ephemeral=True)
                return
            
            new_matches = []
            
            try:
                
                # add the user to the game's queue
                res = requests.get(
                    API_URL + f"/queue/{self.game_id}/{interaction.user.id}"
                )
                
                if not res.ok:
                    raise Exception(res.text)
                        
                # the endpoint returns newly created matches
                new_matches = res.json()
                
            except Exception as e:
                await interaction.followup.send(f"Failed to join {self.game_name} queue: {e}", ephemeral=True)
                # raise e   
                
            if len(new_matches) != 0:   
                # create new matches if we have any
                match_cog = self.bot.get_cog("Match")               
                for match in new_matches:
                    await match_cog.create_new_match(match)
            
            elif self.game_name: # if we're not leaving queue
                await interaction.followup.send(f"Joined {self.game_name} queue", ephemeral=True)
            else:                      
                await interaction.followup.send(f"Left queue", ephemeral=True)
             
    
    @commands.slash_command()
    async def create_queues(self, ctx):
        
        channel = ctx.channel
        
        if channel.id != QUEUE_CHANNEL_ID:
            await ctx.respond("This command can only be used in the queue channel", ephemeral=True)
            return
        
        await channel.purge()
        
        for game in self.bot.games:
            await channel.send(f"{game['game_name']} queue", view=self.QueueView(self.bot, game))
            
        # also send a leave queue
        await channel.send("Leave queue", view=self.QueueView(self.bot, None))
            
        await ctx.respond("Queues created", ephemeral=True)
        

def setup(bot):
    bot.add_cog(Queue(bot))