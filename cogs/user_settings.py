import discord
from discord.ext import commands

import requests

from config import API_URL


class UserSettings(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command()
    async def youtube(self, ctx, yt_username):
        
        discord_id = ctx.author.id
        
        try: 
            res = requests.post(
                API_URL + f"/player/",
                json={
                    "discord_id": discord_id,
                    "username": ctx.author.name,
                    "yt_username": yt_username,
                }
            )
            
            if not res.ok:
                raise Exception(res.text)
                
            
            await ctx.respond(f"Successfully linked YouTube account: @{yt_username}", ephemeral=True)
                    
            if res.status_code == 201:
                await ctx.respond(f"{res.json()['username']} is now a WiiGolfQ user: you can now queue for matches. Make sure you're streaming before you join a queue", ephemeral=True)
            
        except Exception as e:
            await ctx.respond(f"Failed to link YouTube account: {e}", ephemeral=True)
            
            
        # change the yt username for any match this player is in        
        for match in self.bot.active_matches:
            
            if discord_id == match['p1']['discord_id']:
                match['p1']['yt_username'] = yt_username
                break # theoretically someone should only be in one match at a time
            
            if discord_id == match['p2']['discord_id']:
                match['p2']['yt_username'] = yt_username
                break # theoretically someone should only be in one match at a time 
            

def setup(bot):
    bot.add_cog(UserSettings(bot))