import discord
import os
import logging
import requests
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



games = requests.get(API_URL + "/game").json()

active_matches = []




class QueueView(discord.ui.View):
    
    def __init__(self, game):
        super().__init__(timeout=30)
        if game:
            self.game_id = game['game_id']
            self.game_name = game['game_name']
        else:
            self.game_id = 0
            self.game_name = None
    
    @discord.ui.button(emoji="⛳", style=discord.ButtonStyle.secondary)
    async def button_callback(self, button, interaction):
        
        await interaction.response.defer(ephemeral=True)
        
        try:
               
            # add the user to the game's queue
            res = requests.get(
                API_URL + f"/queue/{self.game_id}/{interaction.user.id}"
            )
            
            if not res.ok:
                raise Exception(res.text)
                      
            # the endpoint returns newly created matches
            new_matches = res.json()
                        
            for match in new_matches:
                await create_new_match(match)
             
            if self.game_name:
                if len(new_matches) == 0:
                    await interaction.followup.send(f"Joined {self.game_name} queue", ephemeral=True) 
            else:                      
                await interaction.followup.send(f"Left queue", ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"Failed to join {self.game_name} queue: {e}", ephemeral=True)
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
        
    # also send a leave queue
    await channel.send("Leave queue", view=QueueView(None))
        
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
    try: 
        parent = ctx.channel.parent
    except:
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
        
        if discord_id == match['p1']['discord_id']:
            winner = 2
            loser = 1
        elif discord_id == match['p2']['discord_id']:
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
            
            await message.edit(f"{match[f'p{loser}']['username']} has forfeited. Closing match...", view=None)
            
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
    message = await channel.send(f"Match #{match['match_id']}: {match['p1']['username']} vs. {match['p2']['username']}")
    thread = await message.create_thread(name=match['match_id'], auto_archive_duration=1440)
    await thread.send(f"<@{match['p1']['discord_id']}> <@{match['p2']['discord_id']}> Your {match['game']['game_name']} match is ready!")   

    await send_predictions(thread, match)

    found_1 = await check_live(thread, match, 1)
    found_2 = await check_live(thread, match, 2)
    


async def check_live(channel, match, player):
    
    yt_username = match[f'p{player}']['yt_username'] # player = 1 or 2
    
    url = f"https://www.youtube.com/@{yt_username}/live"
    
    try:
        
        # check if the url redirects
        
        res = requests.get(url)
        
        soup = BeautifulSoup(res.text, 'html.parser')
                
        # the url shows the current livestream if you're streaming
        # or your vods if you're not streaming
        # we're looking for this meta element to see if you are streaming
        # and also keep it for later since we need the start date
        start_time_el = soup.find('meta', {'itemprop': 'startDate'})
                                
        if start_time_el is None: # if they are not live
            await channel.send(f"{match[f'p{player}']['username']} is not live on YouTube")
            return False
                
        video_id = soup.find('meta', {'itemprop': 'identifier'})['content']
        
        # calculate number of seconds to include in url
        start_time = datetime.fromisoformat(start_time_el['content'])
        now_time = datetime.now(timezone.utc)
        seconds_between = int((now_time - start_time).total_seconds())
        
        video_url = f"https://youtu.be/{video_id}?t={seconds_between}"
        
        res = requests.put(
            API_URL + f"/match/{channel.name}/", 
            json={
                f"p{player}_video_url": video_url,
            } 
        )
        
        if not res.ok:
            raise Exception(res.text)
        
        await channel.send(f"{match[f'p{player}']['username']} is live on YouTube. Their video URL is {video_url}")
        return True
        
    except Exception as e:
        await channel.send(f"Failed to check if {match[f'p{player}']['username']} is live: {e}")
        return False

        
async def send_predictions(thread, match):
    
    def float_to_percent(value):
        return f"{value * 100:.1f}%"
    
    elo_predictions = match['predictions']['elo']
    
    p1_win_prob = match['predictions']['p1_win_prob']
    p2_win_prob = float_to_percent(1 - p1_win_prob)
    p1_win_prob = float_to_percent(p1_win_prob)
    
    new_elos = {}
    deltas = {}
             
    for key, value in elo_predictions.items():
        new_elos[key] = [item[0] for item in value]
        deltas[key] = [item[1] for item in value]

    message = f"## Predictions\n"
    message += f"The math gods give {match['p1']['username']} a **{p1_win_prob}** win probability, likewise giving {match['p2']['username']} a **{p2_win_prob}** win probability."
    message += "\n\n"
    message += f"If {match['p1']['username']} wins, your new elos will be **{new_elos['1'][0]} ({deltas['1'][0]})** and **{new_elos['1'][1]} ({deltas['1'][1]})** respectively."
    message += "\n"
    message += f"If {match['p2']['username']} wins, your new elos will be **{new_elos['2'][0]} ({deltas['2'][0]})** and **{new_elos['2'][1]} ({deltas['2'][1]})** respectively."
    message += "\n"
    message += f"In the event of a draw, your new elos will be **{new_elos['D'][0]} ({deltas['D'][0]})** and **{new_elos['D'][1]} ({deltas['D'][1]})** respectively."
    

    await thread.send(message)
        
        
    
    

async def are_you_sure(ctx, prompt="Are you sure?"):
        
    view = AreYouSureView(ctx.author.id)
    message = await ctx.respond(prompt, view=view, ephemeral=True)
    await view.wait()  # Wait for the View to stop interacting.
    
    return view.value, message  # True if the confirm button was pressed.

        
        

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)