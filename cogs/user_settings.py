import discord
from discord.ext import commands
from discord.ui import Select, View

import requests

from config import API_URL


class QueueForView(View):
    class QueueForSelect(Select):
        def __init__(self, bot):
            self.bot = bot

            super().__init__(
                placeholder="I want to play... (select 1 or more)",
                min_values=1,
                max_values=len(self.bot.games),
                options=[
                    discord.SelectOption(label=game["game_name"])
                    for game in self.bot.games
                ],
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            names = self.values

            if "NSS Score (9 Hole Random)" in names and len(names) > 1:
                await interaction.followup.send(
                    "NSS Score (9 Hole Random) must be alone", ephemeral=True
                )
                return

            queues_for = []
            for name in names:
                # find the game in self.bot.games
                found = next(
                    (game for game in self.bot.games if game["game_name"] == name), None
                )
                queues_for.append(found["game_id"])

            try:
                res = requests.patch(
                    API_URL + f"/player/{interaction.user.id}",
                    json={"queues_for": queues_for},
                )

                if not res.ok:
                    raise Exception(res.text)

                await interaction.followup.send(
                    f"You will queue for {', '.join(names)}", ephemeral=True
                )
            except Exception as e:
                await interaction.followup.send(
                    f"Failed to select games: {e}", ephemeral=True
                )

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

        self.add_item(self.QueueForSelect(bot))


class UserSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command()
    @discord.option(
        "handle",
        description="Your YouTube handle",
        required=True,
    )
    @discord.option(
        "url",
        description="Your YouTube URL",
        required=False,
    )
    async def youtube(self, ctx, handle, url):
        def extract_id_from_url(url):
            things_before_id = [
                "youtube.com/watch?v=",
                "youtube.com/live/",
                "youtu.be/",
            ]
            for thing in things_before_id:
                if thing in url:
                    return url.split(thing)[1].split("&")[0]

            raise Exception("Invalid YouTube URL")

        discord_id = ctx.author.id

        try:
            youtube = {}

            if handle:
                youtube["handle"] = handle

            if url:
                video_id = extract_id_from_url(url)
                youtube["video_id"] = video_id

            res = requests.post(
                API_URL + f"/player/{discord_id}",
                json={
                    "discord_id": discord_id,
                    "username": ctx.author.name,
                    "youtube": youtube,
                },
            )

            if not res.ok:
                print(res.status_code)
                raise Exception(res.text)

            await ctx.respond(
                f"Successfully linked YouTube account: @{handle}", ephemeral=True
            )

            if res.status_code == 201:
                await ctx.respond(
                    f"{res.json()['username']} is now a WiiGolfQ user: you can now queue for matches. Make sure you're streaming before you join a queue",
                    ephemeral=True,
                )

        except Exception as e:
            await ctx.respond(f"Failed to link YouTube account: {e}", ephemeral=True)

    @discord.slash_command()
    async def queue_for(self, ctx):
        await ctx.respond(
            "Select the game you want to queue for",
            view=QueueForView(self.bot),
            ephemeral=True,
        )


def setup(bot):
    bot.add_cog(UserSettings(bot))
