import discord
from discord.ext import commands
from discord import PermissionOverwrite, option

import requests
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from config import API_URL
from utils import are_you_sure, send_table

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
            
            match = next((m for m in self.bot.active_matches if m['discord_thread_id'] == ctx.channel.id), None)
            
            # res = requests.get(
            #     API_URL + f"/match/{ctx.channel.name}/"
            # )
            
            # if not res.ok:
            #     raise Exception(res.text)
            
            # match = res.json()
            
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
            raise e
            # if res:
            #     soup = BeautifulSoup(res.text, 'html.parser')
            #     await ctx.respond(f"Failed to forfeit match: {soup.find('body').text[:1950]}", ephemeral=True)
            # else:
            #     await ctx.respond(f"Failed to forfeit match: {e}", ephemeral=True)
            
            
    async def create_new_match(self, match):
    
        # TODO: add an env variable for matches channel
        channel = self.bot.get_channel(1209994140969082931)
        
        # get the tag for the game
        tag = next((tag for tag in channel.available_tags if tag.name == match['game']['shortcode']), None)
        
        thread = await channel.create_thread(
            name=match['match_id'], 
            auto_archive_duration=1440,
            applied_tags=[tag],
            content=f"{match['game']['game_name']}: {match['p1']['username']} (<@{match['p1']['discord_id']}>) vs. {match['p2']['username']} (<@{match['p2']['discord_id']}>)"
        )
        
        # we also create a new vc channel for the match
        vc = await channel.guild.create_voice_channel(
            name=match['match_id'],
            category=channel.category,
            user_limit=2,
        )
        
        # we also give p1 and p2 permissions to connect
        p1 = channel.guild.get_member(match['p1']['discord_id'])
        p2 = channel.guild.get_member(match['p2']['discord_id'])
        
        # TODO: not really sure if this is a good idea
        # im only doing this because im using not real users for testing
        if p1:
            await vc.set_permissions(p1, connect=True)
        if p2:
            await vc.set_permissions(p2, connect=True)
        
        match['discord_thread_id'] = thread.id
        
        match['agrees'] = [False, False] 
        
        self.bot.active_matches.append(match)

        try:
            requests.put(
                API_URL + f"/match/{match['match_id']}", 
                json={
                    "discord_thread_id": thread.id,
                }
            )   
        except Exception as e:
            await thread.send(f"Failed to update match thread: {e}")
            print(f"Exception in create_new_match: {e}")
        
        # await thread.send(f"<@{match['p1']['discord_id']}> <@{match['p2']['discord_id']}> Your {match['game']['game_name']} match is ready.")   

        await self.send_predictions(match)
        
        await self.live_procedure(match)
        
    async def send_predictions(self, match):
                
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
        
        thread = self.bot.get_channel(match['discord_thread_id'])
        
        await send_table(thread, "Predictions", cols)
        
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
                API_URL + f"/match/{thread.name}", 
                json={
                    "status": "Ongoing",      
                }  
            )
            
            if not res.ok:
                raise Exception(res.text)
            
            await thread.send("## This match is now ongoing.\nCoordinate with your opponent to start your speedruns at approximately the same time, then after finishing use **/report** to report your score.\n## GLHF!")
            
        except Exception as e:
            await thread.send(f"Failed to update match status: {e}")
            print(f"Exception in ongoing_procedure: {e}")  # Add this line
            return
        
    @commands.slash_command()
    @option(
        "score",
        description="Your score (score matches only)",
        required=False,
        type=str
    )
    @option(
        "start",
        description="Your start debug info (speedrun matches only)",
        required=False,
        type=str
    )
    @option(
        "end",
        description="Your end debug info (speedrun matches only)",
        required=False,
        type=str
    )
    @option(
        "fps",
        description="Your video FPS (speedrun matches only)",
        required=False,
        type=int
    )
    async def report(self, ctx, score, start, end, fps):
        
        match_id = int(ctx.channel.name)
        match = next((m for m in self.bot.active_matches if m['match_id'] == match_id), None)
        
        # check if match is ongoing
        if match is None or (match['status'] != "Ongoing" and match['status'] != "Waiting for agrees"):
            await ctx.respond("This match is not ongoing", ephemeral=True)
            return
        
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
        
        # get the match's game
        game_name = match['game']['game_name']
        game = next((g for g in self.bot.games if g['game_name'] == game_name), None)
        
        if game['speedrun']:
            
            if not start or not end or not fps:
                await ctx.respond("You must provide start, end, and fps", ephemeral=True)
                return
            
            if score:
                await ctx.respond("Don't provide a score for a speedrun match", ephemeral=True)
                return
                
            fps = int(fps)

            if not (fps == 30 or fps == 60):
                await ctx.respond("FPS must be 30 or 60", ephemeral=True)
                return
            
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
    
        else:
            
            if not score:
                await ctx.respond("You must provide a score", ephemeral=True)
                return
            if start or end or fps:
                await ctx.respond("Don't provide start, end, and fps for a score match", ephemeral=True)
                return
            
            sign, number = score[0], score[1:]
            
            if not number.isdigit():
                await ctx.respond("Invalid score", ephemeral=True)
                return

            if sign == '-':
                score = -int(number)
            elif sign == '+':
                score = int(number)
            elif sign.isdigit():
                score = int(score)
            else:
                await ctx.respond("Invalid score", ephemeral=True)
                return
            
            await ctx.respond(f"Reporting a score of {score}...", ephemeral=True)
                    
        await self.report_score(match, player, score)
            
    async def report_score(self, match, player, score):
        
        thread = self.bot.get_channel(match['discord_thread_id'])
        
        match_id = match['match_id']
        discord_id = match[f'p{player}']['discord_id']
        
        try:
            res = requests.get(
                API_URL + f"/report/{match_id}",
                params={
                    "player": discord_id,
                    "score": score,
                }
            )
            match = res.json()
            print(match)
            
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
                API_URL + f"/match/{match_id}", 
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
            
        message += "Use **/agree** to confirm the results. Use **/disagree** to dispute the results. Use **/report** again to resubmit your score."
        
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
                API_URL + f"/match/{thread.name}", 
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
            
        
        # TODO: add an env variable for matches channel
        channel = self.bot.get_channel(1209994140969082931)
        thread = channel.get_thread(match['discord_thread_id'])
        match_id = match['match_id']
                    
        res = requests.put(
            API_URL + f"/match/{match_id}", 
            json={
                "status": "Finished",
                "forfeited_player": forfeited_player, # either "1" or "2"
            } 
        )
        
        match = res.json()
        
        if not res.ok:
            raise Exception(res.text)   
        
        
        
        await self.send_results(match)
        
        # lock the match thread
        await thread.edit(archived=True, locked=True)
        
        # first look for a vc channel with the same name as the match id
        vc = discord.utils.get(channel.guild.voice_channels, name=str(match_id))     
        # then delete it
        if vc:
            await vc.delete()     
        
        # remove match from active_matches
        for m in self.bot.active_matches:
            if m['match_id'] == match_id:
                self.bot.active_matches.remove(m)
                break
            
                
            
    async def send_results(self, match):
        
        
        elo_predictions = match['predictions']['elo']
        
        result = match['result']
        
        cols = [
            [
                "⠀", 
                "**Elo before**", 
                "**Elo after**", 
            ],
            [
                f"__**{match['p1']['username']}**__",
                f"{match['p1_mu_before']}",
                f"{elo_predictions[result][0][0]} ({elo_predictions[result][0][1]})", # new elo (delta)
            ],
            [
                f"__**{match['p2']['username']}**__",
                f"{match['p2_mu_before']}",
                f"{elo_predictions[result][1][0]} ({elo_predictions[result][1][1]})",
            ],
        ]
                
        # TODO: add an env variable for matches channel
        channel = self.bot.get_channel(1209994140969082931)
        
        thread = channel.get_thread(match['discord_thread_id'])
        await send_table(thread, "Results", cols)

        
        
        
        
   
        
        
        
       
        
    
        



def setup(bot):
    bot.add_cog(Match(bot))        
            
            
        
        
