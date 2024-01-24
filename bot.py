import discord
import os
import logging
import requests
import googleapiclient.discovery
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from bs4 import BeautifulSoup

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

bot = discord.Bot()

API_URL = os.environ.get("WGL_API_URL")

GUILD_ID = int(os.environ.get("GUILD_ID"))
QUEUE_CHANNEL_ID = int(os.environ.get("QUEUE_CHANNEL_ID"))


YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

youtube = googleapiclient.discovery.build(
    "youtube", "v3", developerKey = YOUTUBE_API_KEY)




games = requests.get(API_URL + "/game").json()

active_matches = []




class QueueView(discord.ui.View):
    
    def __init__(self, game):
        super().__init__()
        self.game = game
    
    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger)
    async def button_callback(self, button, interaction):
        
        await interaction.response.defer(ephemeral=True)
                
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
                raise Exception(res.text)
                      
            # the endpoint returns newly created matches
            new_matches = res.json()
                        
            for match in new_matches:
                await create_new_match(match)
                                
            await interaction.followup.send(f"Joined {self.game['game_name']} queue", ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"Failed to join {self.game['game_name']} queue: {e}", ephemeral=True)
            # raise e
    
class AreYouSureView(discord.ui.View):
    
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id
    
    @discord.ui.button(label='Yes', style=discord.ButtonStyle.success)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        if self.check(interaction):
            await interaction.response.defer()
            self.value = True
            self.stop()
        else:
            await interaction.response.send_message("This confirmation is not yours", ephemeral=True)
        
    @discord.ui.button(label='No', style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        if self.check(interaction):
            await interaction.response.defer()
            self.value = False
            self.stop()
        else:
            await interaction.response.send_message("This confirmation is not yours", ephemeral=True)
        
    def check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user_id
    
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
            raise Exception(res.text)
            
        
        await ctx.respond(f"Successfully linked YouTube account: {yt_username}", ephemeral=True)
                
        if res.status_code == 201:
            await ctx.respond(f"{res.json()['username']} is now a WGL user - you can now queue for matches. Make sure you're streaming before you join a queue", ephemeral=True)
        
    except Exception as e:
        await ctx.respond(f"Failed to link YouTube account: {e}", ephemeral=True)
        return
    
@bot.slash_command(guild_ids=[GUILD_ID])
async def forfeit(ctx):
    
    await ctx.defer()
    
    discord_id = ctx.author.id
    
    # check if we are in a thread
    if not ctx.channel.parent:
        await ctx.respond("This command can only be used in a match thread", ephemeral=True)
        return
    
    # check if the player is actually playing in the match
    try:
        res = requests.get(
            API_URL + f"/match/{ctx.channel.name}/"
        )
        
        if not res.ok:
            raise Exception(res.text)
        
        match = res.json()
        
        if discord_id == match['player_1']['discord_id']:
            winner = 2
            loser = 1
        elif discord_id == match['player_2']['discord_id']:
            winner = 1
            loser = 2
        else:
            await ctx.respond("You are not playing in this match", ephemeral=True)
            return
        
        # ask if you're sure
        
        confirmation, message = await are_you_sure(ctx)
                
        if confirmation:
            res = requests.put(
                API_URL + f"/match/{ctx.channel.name}/", 
                json={
                    "status": "Finished",
                    "result": f"{winner}",
                } 
            )
                            
            if not res.ok:
                raise Exception(res.text)
                
            match = res.json()
            
            await message.edit(f"{match[f'player_{loser}']['username']} has forfeited. Closing match...", view=None)
            
            thread = bot.get_channel(ctx.channel.id)
            await thread.edit(archived=True, locked=True)
            
        else:
            await message.edit("Forfeit cancelled.", view=None)
            return    
    
    except Exception as e:
        await ctx.respond(f"Failed to forfeit match: {e}", ephemeral=True)
        return
        
async def create_new_match(match):    
    channel = bot.get_channel(1199197176740454441)
    message = await channel.send(f"Match #{match['match_id']}: {match['player_1']['username']} vs. {match['player_2']['username']}")
    thread = await message.create_thread(name=match['match_id'], auto_archive_duration=1440)
    await thread.send(f"<@{match['player_1']['discord_id']}> <@{match['player_2']['discord_id']}> Your {match['game']['game_name']} match is ready!")   

    found_1 = await check_live(thread, match, 1)
    found_2 = await check_live(thread, match, 2)
    


async def check_live(channel, match, player):
    
    yt_username = match[f'player_{player}']['yt_username']
    
    url = f"https://www.youtube.com/@{yt_username}/live"
    
    try:
        
        # check if the url redirects
        
        res = requests.get(url)
        
        soup = BeautifulSoup(res.text, 'html.parser')
                
        # this start date will appear on live broadcasts
        start_time_el = soup.find('meta', {'itemprop': 'startDate'})
        print(start_time_el)
                                
        if start_time_el is None: # if they are not live
            await channel.send(f"{match[f'player_{player}']['username']} is not live on YouTube")
            return False
                
        video_id = soup.find('meta', {'itemprop': 'identifier'})['content']
        print(video_id)
        
        # calculate number of seconds to include in url
        start_time = datetime.fromisoformat(start_time_el['content'])
        now_time = datetime.now(timezone.utc)
        seconds_between = int((now_time - start_time).total_seconds())
        
        video_url = f"https://youtu.be/{video_id}?t={seconds_between}"
        
        res = requests.put(
            API_URL + f"/match/{channel.name}/", 
            json={
                f"player_{player}_video_url": video_url,
            } 
        )
        
        if not res.ok:
            raise Exception(res.text)
        
        await channel.send(f"{match[f'player_{player}']['username']} is live on YouTube. Their video URL is {video_url}")
        return True
        
    except Exception as e:
        await channel.send(f"Failed to check if {match[f'player_{player}']['username']} is live: {e}")
        return False
        
    
        
        
        
    
    

async def are_you_sure(ctx, prompt="Are you sure?"):
        
    view = AreYouSureView(ctx.author.id)
    message = await ctx.respond(prompt, view=view, ephemeral=True)
    await view.wait()  # Wait for the View to stop interacting.
    
    return view.value, message  # True if the confirm button was pressed.

        
        

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)