import discord
import os
import logging
import requests

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

bot = discord.Bot()

API_URL = os.environ.get("WGL_API_URL")

GUILD_ID = int(os.environ.get("GUILD_ID"))
QUEUE_CHANNEL_ID = int(os.environ.get("QUEUE_CHANNEL_ID"))

games = requests.get(API_URL + "/game").json()

class QueueView(discord.ui.View):
    
    def __init__(self, game):
        super().__init__()
        self.game = game
    
    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def button_callback(self, button, interaction):
                
        if button.label == "Join":
            game_id = self.game["game_id"]
        else:
            game_id = 0
        
        try:
               
            # add the user to the game's queue
            res = requests.get(
                API_URL + f"/queue/{game_id}/{interaction.user.id}"
            )
            
            if not res.ok:
                raise requests.exceptions.HTTPError(res.text)
                      
            # the endpoint returns newly created matches
            new_matches = res.json()
                        
            for match in new_matches:
                await create_new_match(match)
                                
            await interaction.response.send_message(f"Joined {self.game['game_name']} queue", ephemeral=True)
        
        except requests.exceptions.HTTPError as e:
            await interaction.response.send_message(f"Failed to join {self.game['game_name']} queue: {e}", ephemeral=True)
        
@bot.event
async def on_ready():   
    print(f'{bot.user.name} has connected to Discord')

@bot.slash_command(guild_ids=[GUILD_ID])
async def create_queues(ctx):
    
    channel = ctx.channel
    
    if channel.id != QUEUE_CHANNEL_ID:
        await ctx.respond("This command can only be used in the queue channel", ephemeral=True)
        return
    
    await channel.purge()
    
    for game in games:
        await channel.send(f"{game['game_name']} queue", view=QueueView(game))
        
    await ctx.respond("Queues created", ephemeral=True)
    

@bot.slash_command(guild_ids=[GUILD_ID])
async def youtube(ctx, yt_username):
    
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
            raise requests.exceptions.HTTPError(res.text)
            
        
        await ctx.respond(f"Successfully linked YouTube account: {yt_username}", ephemeral=True)
                
        if res.status_code == 201:
            await ctx.respond(f"{res.json()['username']} is now a WGL user - you can now queue for matches. Make sure you're streaming before you join a queue", ephemeral=True)
        
    except requests.exceptions.HTTPError as e:
        await ctx.respond(f"Failed to link YouTube account: {e}", ephemeral=True)
        return
        
async def create_new_match(match):    
    channel = bot.get_channel(1199197176740454441)
    message = await channel.send(f"Match #{match['match_id']}: {match['player_1']['username']} vs. {match['player_2']['username']}")
    thread = await message.create_thread(name=f"Match #{match['match_id']}", auto_archive_duration=1440)
    await thread.send(f"<@{match['player_1']['discord_id']}> <@{match['player_2']['discord_id']}> Your {match['game']['game_name']} match is ready!")

        
        

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)