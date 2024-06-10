import discord
from discord.ext import commands
from discord import option

import requests
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from config import API_URL, MATCH_CHANNEL_ID
from utils import are_you_sure, send_table, generate_agree_list


class Match(commands.Cog):
    class ReportScoreModal(discord.ui.Modal):
        def __init__(self, cog, *args, **kwargs):
            super().__init__(title="Report score", *args, **kwargs)
            self.cog = cog
            self.add_item(
                discord.ui.InputText(label="Score", placeholder="Enter your score")
            )

        async def callback(self, interaction: discord.Interaction):
            pass

    class ReportTimeModal(discord.ui.Modal):
        def __init__(self, cog, *args, **kwargs):
            super().__init__(title="Report time", *args, **kwargs)
            self.cog = cog
            self.add_item(
                discord.ui.InputText(
                    label="Debug info: start",
                    placeholder="Enter debug info from the start frame",
                )
            )
            self.add_item(
                discord.ui.InputText(
                    label="Debug info: end",
                    placeholder="Enter debug info from the start frame",
                )
            )
            self.add_item(
                discord.ui.InputText(
                    label="FPS", placeholder="Enter FPS of the video (30 or 60)"
                )
            )

        async def callback(self, interaction: discord.Interaction):
            start, end, fps = (child.value for child in self.children)

            if not start or not end or not fps:
                await interaction.response.send_message(
                    "You must provide start, end, and fps", ephemeral=True
                )
                return

            await Match.calculate_score(
                self.cog, interaction, start=start, end=end, fps=fps
            )

    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command()
    async def forfeit(self, ctx):
        await ctx.defer()

        discord_id = ctx.author.id

        # check if we are in a thread
        try:
            ctx.channel.parent
        except Exception:
            await ctx.respond(
                "This command can only be used in a match thread", ephemeral=True
            )
            return

        # check if the player is actually playing in the match
        try:
            # TODO: change this to use self.bot.active_matches

            match = next(
                (
                    m
                    for m in self.bot.active_matches
                    if m["discord_thread_id"] == ctx.channel.id
                ),
                None,
            )

            target_team = None
            target_tp = None
            # check if the user of the command is playing in the match
            # find the player amongst the teams
            for team in match.get("teams"):
                for tp in team.get("players"):
                    if tp["player"]["discord_id"] == ctx.author.id:
                        target_team = team
                        target_tp = tp
                        break
            if target_tp is None:
                await ctx.respond("You are not playing in this match", ephemeral=True)
                return

            # ask if you're sure

            confirmation, message = await are_you_sure(ctx)

            if confirmation:
                data = {}
                data["teams"] = [
                    {
                        "pk": team["pk"],
                        "forfeited": True if team == target_team else team["forfeited"],
                    }
                    for team in match["teams"]
                ]

                try:
                    res = requests.patch(
                        API_URL + f"/match/{match['match_id']}",
                        json=data,
                    )
                    if not res.ok:
                        raise Exception(res.text)

                    replace = res.json()
                    match.update(replace)

                except Exception as e:
                    await message.edit(
                        f"Failed to forfeit match: {e}",
                        view=None,
                    )
                    return

                await message.edit(
                    f"Team {target_team['team_num']} has forfeited.",
                    view=None,
                )
            else:
                await message.edit("Forfeit cancelled.", view=None)
                return

            # if we get a response back that everyone has a place, go to agree procedure
            if match["status"] == "Waiting for agrees":
                await self.agree_procedure(match)

        except Exception as e:
            raise e

    async def create_new_match(self, match):
        channel = self.bot.get_channel(MATCH_CHANNEL_ID)

        # get the tag for the game
        tag = next(
            (
                tag
                for tag in channel.available_tags
                if tag.name == match["game"]["shortcode"]
            ),
            None,
        )

        content = f"**{match['game']['game_name']}**\n\n__Teams__"

        for team in match.get("teams"):
            content += f"\n- {team.get('team_num')}: "  # bullet point

            for tp in team.get("players"):
                content += (
                    f"{tp['player']['username']} (<@{tp['player']['discord_id']}>), "
                )

            if len(team.get("players")) > 0:
                content = content[:-2]  # remove the final comma+space

        thread = await channel.create_thread(
            name=match["match_id"],
            auto_archive_duration=1440,
            applied_tags=[tag],
            content=content,
        )

        match["discord_thread_id"] = thread.id

        match["agrees"] = generate_agree_list(match, False)

        self.bot.active_matches.append(match)

        try:
            requests.put(
                API_URL + f"/match/{match['match_id']}",
                json={
                    "discord_thread_id": thread.id,
                },
            )
        except Exception as e:
            await thread.send(f"Failed to update match thread: {e}")
            print(f"Exception in create_new_match: {e}")

        await self.live_procedure(match)

    @commands.slash_command()
    async def live(self, ctx):
        await ctx.defer()

        # check if you're in a thread
        try:
            ctx.channel.parent
        except Exception:
            await ctx.respond(
                "This command can only be used in a match thread", ephemeral=True
            )
            return

        # update the match and replace it in active_matches
        match_id = int(ctx.channel.name)
        try:
            replace = requests.get(API_URL + f"/match/{ctx.channel.name}").json()
        except Exception as e:
            await ctx.respond(f"Failed to get match: {e}", ephemeral=True)
            return
        match = next(m for m in self.bot.active_matches if m["match_id"] == match_id)
        match.update(replace)

        if match is None:
            await ctx.respond("This match is not active", ephemeral=True)
            return

        if match["status"] != "Waiting for livestreams":
            await ctx.respond("Livestreams already found", ephemeral=True)
            return

        await ctx.respond("Checking for livestreams...")

        await self.live_procedure(match)

    async def live_procedure(self, match):
        thread = self.bot.get_channel(match["discord_thread_id"])

        one_player_live = False
        all_players_live = True

        for team in match["teams"]:
            for tp in team["players"]:
                video_id, timestamp = await self.check_live(match, tp.get("player"))

                if video_id:
                    tp["video_id"] = video_id
                    tp["video_timestamp"] = timestamp
                    one_player_live = True
                else:
                    all_players_live = False

        try:
            requests.put(API_URL + f"/match/{thread.name}", json=match)
        except Exception as e:
            await thread.send(f"Failed to update match videos: {e}")
            print(f"Exception in live_procedure: {e}")
            return

        game = next(
            g for g in self.bot.games if g["game_id"] == match["game"]["game_id"]
        )
        require_all = game["require_all_livestreams"]

        if all_players_live or (not require_all and one_player_live):
            await self.ongoing_procedure(match)
        else:
            message = ""

            if require_all:
                message += "## Not all players are live."
            else:
                message += "## No players are live."

            message += "\nUse **/live** to check again. Use **/youtube** to change your YouTube information."

            await thread.send(message)

    async def ongoing_procedure(self, match):
        thread = self.bot.get_channel(match["discord_thread_id"])

        match["status"] = "Ongoing"

        try:
            res = requests.put(
                API_URL + f"/match/{thread.name}",
                json={
                    "status": "Ongoing",
                },
            )

            if not res.ok:
                raise Exception(res.text)

            await thread.send(
                "## This match is now ongoing.\nCoordinate with your opponent to start your speedruns at approximately the same time, then after finishing use **/report** to report your score.\n## GLHF!"
            )

        except Exception as e:
            await thread.send(f"Failed to update match status: {e}")
            print(f"Exception in ongoing_procedure: {e}")  # Add this line
            return

    @commands.slash_command()
    async def report(self, ctx):
        # check if we're in a thread
        try:
            ctx.channel.parent
        except Exception:
            await ctx.respond(
                "This command can only be used in a match thread", ephemeral=True
            )
            return

        match_id = int(ctx.channel.name)
        match = next(
            (m for m in self.bot.active_matches if m["match_id"] == match_id), None
        )

        # check if match is ongoing
        if match is None or (
            match["status"] != "Ongoing" and match["status"] != "Waiting for agrees"
        ):
            await ctx.respond("This match is not ongoing", ephemeral=True)
            return

        target_team = None
        target_tp = None
        # check if the user of the command is playing in the match
        # find the player amongst the teams
        for team in match.get("teams"):
            for tp in team.get("players"):
                if tp["player"]["discord_id"] == ctx.author.id:
                    target_team = team
                    target_tp = tp
                    break
        if target_tp is None:
            await ctx.respond("You are not playing in this match", ephemeral=True)
            return

        if target_team["forfeited"]:
            await ctx.respond("You have forfeited", ephemeral=True)
            return

        # get the match's game
        game_name = match["game"]["game_name"]
        game = next((g for g in self.bot.games if g["game_name"] == game_name), None)

        if game["speedrun"]:
            await ctx.send_modal(self.ReportTimeModal(self))
        else:
            await ctx.send_modal(self.ReportScoreModal(self))

    async def calculate_score(
        self, interaction, score=None, start=None, end=None, fps=None
    ):
        match_id = int(interaction.channel.name)
        match = next(
            (m for m in self.bot.active_matches if m["match_id"] == match_id), None
        )

        # get the match's game
        game_name = match["game"]["game_name"]
        game = next((g for g in self.bot.games if g["game_name"] == game_name), None)

        if game["speedrun"]:
            if not start or not end or not fps:
                await interaction.response.send_message(
                    "You must provide start, end, and fps", ephemeral=True
                )
                return

            fps = int(fps)

            if not (fps == 30 or fps == 60):
                await interaction.response.send_message(
                    "FPS must be 30 or 60", ephemeral=True
                )
                return

            def get_ms_from_debug_info(debug_info):
                # there is an attribute called 'vct' in the debug info
                # this is the current time in seconds

                start_index = debug_info.find('"vct": "') + len('"vct": "')
                end_index = debug_info.find('",', start_index)

                # will return -1 if the substring is not found
                if start_index == -1 or end_index == -1:
                    raise Exception("Invalid debug info")

                # get the start and end times in milliseconds (it's initially a string)
                return int(float(debug_info[start_index:end_index]) * 1000)

            try:
                start_ms = get_ms_from_debug_info(start)
                end_ms = get_ms_from_debug_info(end)
            except Exception:
                await interaction.response.send_message(
                    "Invalid debug info", ephemeral=True
                )
                return

            # find time between start and end
            score = end_ms - start_ms

            # round to the start of the nearest frame
            score = int(score - (score % (1000 / fps)) + 0.5)

            await interaction.response.send_message(
                f"The retime resulted in a time of {score}ms", ephemeral=True
            )

        else:  # score match
            if not score:
                await interaction.response.send_message(
                    "You must provide a score", ephemeral=True
                )
                return
            if start or end or fps:
                await interaction.response.send_message(
                    "Don't provide start, end, and fps for a score match",
                    ephemeral=True,
                )
                return

            sign, number = score[0], score[1:]

            if not number.isdigit():
                await interaction.response.send_message("Invalid score", ephemeral=True)
                return

            if sign == "-":
                score = -int(number)
            elif sign == "+":
                score = int(number)
            elif sign.isdigit():
                score = int(score)
            else:
                await interaction.response.send_message("Invalid score", ephemeral=True)
                return

            await interaction.response.send_message(
                f"Reporting a score of {score}...", ephemeral=True
            )

        await self.report_score(match, interaction.user.id, score)

    async def report_score(self, match, tp_discord_id, score):
        thread = self.bot.get_channel(match["discord_thread_id"])

        match_id = match["match_id"]

        try:
            # find the tp to change and change their score
            for team in match.get("teams"):
                for tp in team.get("players"):
                    if tp["player"]["discord_id"] == tp_discord_id:
                        tp["score"] = score
                        username = tp["player"]["username"]
                        break

            # delete score info from every other player
            # so its not updated in the database
            teams_copy = [
                {
                    "pk": team["pk"],
                    "players": [
                        {
                            k: v
                            for k, v in tp.items()
                            if k == "pk"
                            or (
                                k == "score"
                                and tp["player"]["discord_id"] == tp_discord_id
                            )
                        }
                        for tp in team["players"]
                    ],
                }
                for team in match["teams"]
            ]

            res = requests.patch(
                API_URL + f"/match/{match_id}",
                json={"teams": teams_copy},
            )
            if not res.ok:
                raise Exception(res.text)

            match = res.json()
            # find the player's formatted score in the response
            for team in match["teams"]:
                for tp in team.get("players"):
                    if tp["player"]["discord_id"] == tp_discord_id:
                        score_formatted = tp["score_formatted"]

            await thread.send(
                f"{username} has reported a score of **{score_formatted}**."
            )

        except Exception as e:
            await thread.send(f"Failed to report score: {e}")
            print(f"Exception in report_score: {e}")

        if match["status"] == "Waiting for agrees":
            await self.agree_procedure(match)

    async def agree_procedure(self, match):
        thread = self.bot.get_channel(match["discord_thread_id"])

        match_id = match["match_id"]

        # replace match in active_matches with the updated match
        for m in self.bot.active_matches:
            if m["match_id"] == match_id:
                m["status"] = "Waiting for agrees"
                m["agrees"] = generate_agree_list(m, False)
                break

        message = "## The match has finished.\n"

        message += "Use **/agree** to confirm the results. Use **/disagree** to dispute the results. Use **/report** again to resubmit your score."

        await thread.send(message)

        await self.send_results(match)

    async def check_live(self, match, player):
        async def find_video_id_and_timestamp(url):
            try:
                res = requests.get(url)

                soup = BeautifulSoup(res.text, "html.parser")

                # the url shows the current livestream if you're streaming
                # or your vods if you're not streaming
                # we're looking for this meta element to see if you are streaming
                # and also keep it for later since we need the start date
                start_time_el = soup.find("meta", {"itemprop": "endDate"})

                if start_time_el is None:  # if they are not live
                    return None, None

                end_time_el = soup.find("meta", {"itemprop": "endDate"})

                if end_time_el:  # if the stream ended
                    return None, None

                video_id = soup.find("meta", {"itemprop": "identifier"})["content"]

                # find current timestamp
                start_time = datetime.fromisoformat(start_time_el["content"])
                now_time = datetime.now(timezone.utc)
                seconds_between = int((now_time - start_time).total_seconds())

                return video_id, seconds_between

            except Exception:
                print(f"Failed to get {player['username']}'s YouTube page")
                return None

        thread = self.bot.get_channel(match["discord_thread_id"])

        yt = player.get("youtube")
        yt_handle = yt.get("handle")
        yt_video_id = yt.get("video_id")

        # look for a public livestream first
        stream_video_id, timestamp = await find_video_id_and_timestamp(
            f"https://www.youtube.com/@{yt_handle}/live"
        )

        # if not, look for an unlisted livestream
        if not stream_video_id:
            stream_video_id, timestamp = await find_video_id_and_timestamp(
                f"https://www.youtube.com/watch?v={yt_video_id}"
            )

        # if neither are found they are not live
        if not stream_video_id:
            await thread.send(f"{player['username']} is not live on YouTube.")
            return None, None

        video_url = f"https://youtu.be/{stream_video_id}?t={timestamp}"

        await thread.send(f"{player['username']} is live on YouTube at {video_url}")
        return stream_video_id, timestamp

    @commands.slash_command()
    async def agree(self, ctx):
        await ctx.defer()

        match_id = int(ctx.channel.name)
        match = next(
            (m for m in self.bot.active_matches if m["match_id"] == match_id), None
        )

        if match is None:
            await ctx.respond("This match is not active", ephemeral=True)
            return

        discord_id = ctx.author.id

        if match["status"] != "Waiting for agrees":
            await ctx.respond("Both players have not submitted scores", ephemeral=True)
            return

        # find the player's position in match teams
        x, y = None, None
        target_team = None
        target_tp = None
        for i, team in enumerate(match.get("teams")):
            for j, tp in enumerate(team.get("players")):
                if tp["player"]["discord_id"] == discord_id:
                    target_team = team
                    target_tp = tp
                    x, y = i, j

        if target_tp is None:  # if the person using the command isnt in the match
            await ctx.respond("You are not playing in this match", ephemeral=True)
            return

        if target_team["forfeited"]:
            await ctx.respond("Your team has forfeited", ephemeral=True)
            return

        # toggle the player's agreement status
        match["agrees"][x][y] = not match["agrees"][x][y]

        await ctx.respond(
            f"{target_tp['player']['username']}'s agreement status has been toggled to {match['agrees'][x][y]}."
        )

        if match["agrees"] == generate_agree_list(
            match, True
        ):  # if everyone has agreed
            await ctx.send(
                "## All players have agreed to the outcome.\nClosing match..."
            )
            await self.close_match(match)

    async def close_match(self, match):
        channel = self.bot.get_channel(MATCH_CHANNEL_ID)
        thread = channel.get_thread(match["discord_thread_id"])
        match_id = match["match_id"]

        res = requests.put(
            API_URL + f"/match/{match_id}",
            json={
                "status": "Finished",
            },
        )

        if not res.ok:
            raise Exception(res.text)

        match = res.json()

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
            if m["match_id"] == match_id:
                self.bot.active_matches.remove(m)
                break

    async def send_results(self, match):
        """

        Place              1           2
        Team num           2           1
        Score              999         888
        ...

        """

        rows = [["**__Place__**", "**__Team__**", "**__Score__**"]]
        for team in match["teams"]:
            rows.append(
                [
                    f"**{team['place']}**",
                    team["team_num"],
                    team["score_formatted"],
                ]
            )

        channel = self.bot.get_channel(MATCH_CHANNEL_ID)
        thread = channel.get_thread(match["discord_thread_id"])
        await send_table(thread, "Results", rows=rows)

        """
    
        Team 1       xx_Player1_xx       1500 (+150)
                     xx_Player2_xx       1600 (+100)
        Team 2       xx_Player3_xx       1500 (+150)
                     xx_Player4_xx       1600 (+100)
        ...

        """

        rows = [["**__Team__**", "**__Player__**", "**__New elo__**"]]
        for team in match["teams"]:
            for tp in team["players"]:
                rows.append(
                    [
                        "⠀",
                        tp["player"]["username"],
                        f"{tp['mu_after']} ({tp['mu_delta']})",
                    ]
                )

        i = 1
        for team in match["teams"]:
            rows[i][0] = f"**{team['team_num']}**"
            i += match["players_per_team"]

        await send_table(thread, "Elo changes", rows=rows)


def setup(bot):
    bot.add_cog(Match(bot))
