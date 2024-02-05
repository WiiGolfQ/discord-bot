from discord.ext import commands
from discord import Embed

import requests
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from config import API_URL
from utils import are_you_sure

class Match(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.slash_command()
    async def forfeit(self, ctx):
        
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
            # TODO: change this to use self.bot.active_matches
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
                
                await message.edit(f"## {match[f'p{loser}']['username']} has forfeited.\nClosing match...", view=None)
                await self.close_match(match, f"{loser}")
                
            else:
                await message.edit("Forfeit cancelled.", view=None)
                return    
        
        except Exception as e:
            await ctx.respond(f"Failed to forfeit match: {e}", ephemeral=True)
            return
            # if res:
            #     soup = BeautifulSoup(res.text, 'html.parser')
            #     await ctx.respond(f"Failed to forfeit match: {soup.find('body').text[:1950]}", ephemeral=True)
            # else:
            #     await ctx.respond(f"Failed to forfeit match: {e}", ephemeral=True)
            
            
    async def create_new_match(self, match):
    
        # TODO: add matches_channel_id to game object
        channel = self.bot.get_channel(1199197176740454441)
        
        message = await channel.send(f"Match #{match['match_id']}: {match['p1']['username']} vs. {match['p2']['username']}")
        thread = await message.create_thread(name=match['match_id'], auto_archive_duration=1440)
        
        match['discord_thread_id'] = thread.id
        match['agrees'] = [False, True] 
        
        self.bot.active_matches.append(match)

        try:
            requests.put(
                API_URL + f"/match/{match['match_id']}/", 
                json={
                    "discord_thread_id": thread.id,
                }
            )   
        except Exception as e:
            await thread.send(f"Failed to update match thread: {e}")
            print(f"Exception in create_new_match: {e}")
        
        await thread.send(f"<@{match['p1']['discord_id']}> <@{match['p2']['discord_id']}> Your {match['game']['game_name']} match is ready. Your current elos are **{match['p1_mu_before']}** and **{match['p2_mu_before']}** respectively.")   

        await self.send_predictions(match)
        
        await self.live_procedure(match)
        
    @commands.slash_command()
    async def live(self, ctx):
        await ctx.defer()
        
        #check if you're in a thread
        try:
            parent = ctx.channel.parent
        except:
            await ctx.respond("This command can only be used in a match thread", ephemeral=True)
            return
        
        # get the match by match_id
        match_id = int(ctx.channel.name)
        match = next((m for m in self.bot.active_matches if m['match_id'] == match_id), None)
                    
        if match is None:
            await ctx.respond("This match is not active", ephemeral=True)
            return
        
        if (match['status'] != "Waiting for livestreams"):
            await ctx.respond("Livestreams already found", ephemeral=True)
            return
        
        await ctx.respond("Checking for livestreams...")
        
        await self.live_procedure(match)
        
    async def live_procedure(self, match):
            
        thread = self.bot.get_channel(match['discord_thread_id'])
            
        is_p1_live = await self.check_live(match, 1)
        is_p2_live = await self.check_live(match, 2)
        
        if is_p1_live and is_p2_live:
            await self.ongoing_procedure(match)
        else:
            await thread.send("## Both players are not live on YouTube.\nUse **/live** to check again. Use **/youtube** to change your YouTube username. **/cancel** is also available while both livestreams are not detected.")
            
    async def ongoing_procedure(self, match):
    
        thread = self.bot.get_channel(match['discord_thread_id'])
        
        match['status'] = "Ongoing"
            
        try:
            res = requests.put(
                API_URL + f"/match/{thread.name}/", 
                json={
                    "status": "Ongoing",      
                }  
            )
            
            if not res.ok:
                raise Exception(res.text)
            
            await thread.send("## This match is now ongoing.\nCoordinate with your opponent to start your speedruns at approximately the same time, then after finishing use **/retime** to report your score.\n## GLHF!")
            
        except Exception as e:
            await thread.send(f"Failed to update match status: {e}")
            print(f"Exception in ongoing_procedure: {e}")  # Add this line
            return
        
    @commands.slash_command()
    async def retime(self, ctx, start, end, fps): # start and end are youtube debug infos
        
        def get_ms_from_debug_info(debug_info):
            
            # there is an attribute called 'vct' in the debug info
            # this is the current time in seconds
            
        
            start_index = debug_info.find('\"vct\": \"') + len('\"vct\": \"')
            end_index = debug_info.find('\",', start_index)
            
            # will return -1 if the substring is not found
            if start_index == -1 or end_index == -1:
                raise Exception("Invalid debug info")

            
            # get the start and end times in milliseconds (it's initially a string)
            return int(float(debug_info[start_index:end_index]) * 1000)
        
            
        fps = int(fps)

        if not (fps == 30 or fps == 60):
            await ctx.respond("FPS must be 30 or 60", ephemeral=True)
            return
        
        match_id = int(ctx.channel.name)
        match = next((m for m in self.bot.active_matches if m['match_id'] == match_id), None)
            
        # check if we're in a thread
        try:
            parent = ctx.channel.parent
        except:
            await ctx.respond("This command can only be used in a match thread", ephemeral=True)
            return
        
        # check if the player is playing in the match
        if ctx.author.id == match['p1']['discord_id']:
            player = 1
        elif ctx.author.id == match['p2']['discord_id']:
            player = 2
        else:
            await ctx.respond("You are not playing in this match", ephemeral=True)
            return
            
        # check if match is ongoing
        if match['status'] != "Ongoing":
            await ctx.respond("This match is not ongoing", ephemeral=True)
            return
        
        try:
            start_ms = get_ms_from_debug_info(start)
            end_ms = get_ms_from_debug_info(end)
        except:
            await ctx.respond("Invalid debug info", ephemeral=True)
            return
        
        # find time between start and end
        score = end_ms - start_ms
        
        # round to the start of the nearest frame
        score = int(score - (score % (1000 / fps) ) + 0.5)
        
        await ctx.respond(f"The retime resulted in a time of {score}ms", ephemeral=True)
            
        await self.report_score(match, player, score)
            
    async def report_score(self, match, player, score):
        
        thread = self.bot.get_channel(match['discord_thread_id'])
        
        match_id = match['match_id']
        discord_id = match[f'p{player}']['discord_id']
        
        try:
            res = requests.get(
                API_URL + f"/report/{match_id}?player={discord_id}&score={score}"
            )
            match = res.json()
            
            if not res.ok:
                raise Exception(res.text)
        
        except Exception as e:
            await thread.send(f"Failed to report score: {e}")
            print(f"Exception in report_score: {e}")
        
        await thread.send(f"{match[f'p{player}']['username']} has reported a score of **{match[f'p{player}_score_formatted']}**.")
        
        if match['p1_score'] and match['p2_score']:
            await self.agree_procedure(match)
        
    async def agree_procedure(self, match):
        
        thread = self.bot.get_channel(match['discord_thread_id'])
                
        match_id = match['match_id']
                
                        
        try:
            # update status in database
            res = requests.put(
                API_URL + f"/match/{match_id}/", 
                json={
                    "status": "Waiting for agrees",
                } 
            )
            
            if not res.ok:
                raise Exception(res.text)
            
            match = res.json()
            
        except Exception as e:
            await thread.send(f"Failed to update match status: {e}")
            print(f"Exception in agree_procedure: {e}")
            
        # replace match in active_matches with the updated match
        for m in self.bot.active_matches:
            if m['match_id'] == match_id:
                m.update(match)  
                m['agrees'] = [False, False] # set the agrees back to False so you can't pull a fast one
                break
        
        if match['p1_score'] < match['p2_score']:
            winner = 1
            loser = 2
        elif match['p2_score'] < match['p1_score']:
            winner = 2
            loser = 1
        else:
            winner = 0
            loser = 0
            
        message = "## Both players have reported scores.\n"
        
        if winner != loser:
            message += f"{match[f'p{winner}']['username']} has won the match with a score of **{match[f'p{winner}_score_formatted']}**, beating {match[f'p{loser}']['username']}'s score of **{match[f'p{loser}_score_formatted']}**.\n\n"
        else:
            message += f"The match is a draw, with both players scoring **{match['p1_score']}**.\n\n"
            
        message += "Use **/agree** to confirm the results. Use **/disagree** to dispute the results. Use **/retime** again to resubmit your score."
        
        await thread.send(message)
        
    async def check_live(self, match, player):
    
        thread = self.bot.get_channel(match['discord_thread_id'])
        
        yt_username = match[f'p{player}']['yt_username'] # player = 1 or 2
        
        url = f"https://www.youtube.com/@{yt_username}/live"
        
        try:
                    
            res = requests.get(url)
            
            soup = BeautifulSoup(res.text, 'html.parser')
                    
            # the url shows the current livestream if you're streaming
            # or your vods if you're not streaming
            # we're looking for this meta element to see if you are streaming
            # and also keep it for later since we need the start date
            start_time_el = soup.find('meta', {'itemprop': 'startDate'})
                                    
            if start_time_el is None: # if they are not live
                await thread.send(f"{match[f'p{player}']['username']} is not live on YouTube")
                return False
                    
            video_id = soup.find('meta', {'itemprop': 'identifier'})['content']
            
            # calculate number of seconds to include in url
            start_time = datetime.fromisoformat(start_time_el['content'])
            now_time = datetime.now(timezone.utc)
            seconds_between = int((now_time - start_time).total_seconds())
            
            video_url = f"https://youtu.be/{video_id}?t={seconds_between}"
            
            res = requests.put(
                API_URL + f"/match/{thread.name}/", 
                json={
                    f"p{player}_video_url": video_url,
                } 
            )
            
            if not res.ok:
                raise Exception(res.text)
            
            await thread.send(f"{match[f'p{player}']['username']} is live on YouTube at {video_url}")
            return True
            
        except Exception as e:
            await thread.send(f"Failed to check if {match[f'p{player}']['username']} is live: {e}")
            return False

            
    async def send_predictions(self, match):
        
        thread = self.bot.get_channel(match['discord_thread_id'])
        
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
            
        # TODO: make this into its own util function    
        
        embed = Embed(title="Predictions", color=0x00ff00)
        
        cols = [
            [
                "⠀", 
                "**Current elo**", 
                f"**New elo ({match['p1']['username']} wins)**", 
                f"**New elo ({match['p2']['username']} wins)**", 
                f"**New elo (draw)**", 
                "**Estimated win percent**"
            ],
            [
                f"__**{match['p1']['username']}**__",
                f"{match['p1_mu_before']}",
                f"{new_elos['1'][0]} ({deltas['1'][0]})",
                f"{new_elos['2'][0]} ({deltas['2'][0]})",
                f"{new_elos['D'][0]} ({deltas['D'][0]})",
                f"{p1_win_prob}",
            ],
            [
                f"__**{match['p2']['username']}**__",
                f"{match['p2_mu_before']}",
                f"{new_elos['1'][1]} ({deltas['1'][1]})",
                f"{new_elos['2'][1]} ({deltas['2'][1]})",
                f"{new_elos['D'][1]} ({deltas['D'][1]})",
                f"{p2_win_prob}",  
            ],
        ]
        
        
        for i in range(len(cols)):
            # join 1-i with \n
            embed.add_field(name=cols[i][0], value="\n".join([cols[i][j] for j in range(1, len(cols[i]))]), inline=True)
        
        await thread.send(embed=embed)
        
        
    @commands.slash_command()
    async def agree(self, ctx):
        
        await ctx.defer()
        
        match_id = int(ctx.channel.name)
        match = next((m for m in self.bot.active_matches if m['match_id'] == match_id), None)
        
        if match is None:
            await ctx.respond("This match is not active", ephemeral=True)
            return
        
        discord_id = ctx.author.id
        
        if discord_id == match['p1']['discord_id']:
            player = 1
        elif discord_id == match['p2']['discord_id']:
            player = 2
        else:
            await ctx.respond("You are not playing in this match", ephemeral=True)
            return
                
        if match['status'] != "Waiting for agrees":
            await ctx.respond("Both players have not submitted scores", ephemeral=True)
            return
        
        #toggle the player's agreement
        match['agrees'][player - 1] = not match['agrees'][player - 1]
    
        await ctx.respond(f"{match[f'p{player}']['username']}'s agreement status has been toggled to {match['agrees'][player - 1]}.")
        
        if match['agrees'] == [True, True]:
            await ctx.send("## Both players have agreed to the outcome.\nClosing match...")
            await self.close_match(match)
    
    async def close_match(self, match, forfeited_player=None):
        
        thread = self.bot.get_channel(match['discord_thread_id'])
        
        await thread.edit(archived=True, locked=True)
        
        match_id = match['match_id']
        
        # remove match from active_matches
        for m in self.bot.active_matches:
            if m['match_id'] == match_id:
                self.bot.active_matches.remove(m)
                break
            
        try:
                        
            res = requests.put(
                API_URL + f"/match/{match_id}/", 
                json={
                    "status": "Finished",
                    "forfeited_player": forfeited_player, # either "1" or "2"
                } 
            )
            
            if not res.ok:
                raise Exception(res.text)
            
        except Exception as e:
            
            await thread.send(f"Failed to close match: {e}")
            print(f"Exception in close_match: {e}")
            
        
        
        
        
       
        
    
        



def setup(bot):
    bot.add_cog(Match(bot))        
            
            
        
        
