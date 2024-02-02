import discord
from discord.ext import commands

import requests

from config import API_URL, GUILD_ID


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
                
            
            await ctx.respond(f"Successfully linked YouTube account: {yt_username}", ephemeral=True)
                    
            if res.status_code == 201:
                await ctx.respond(f"{res.json()['username']} is now a WiiGolfQ user: you can now queue for matches. Make sure you're streaming before you join a queue", ephemeral=True)
            
        except Exception as e:
            await ctx.respond(f"Failed to link YouTube account: {e}", ephemeral=True)
            

def setup(bot):
    bot.add_cog(UserSettings(bot))