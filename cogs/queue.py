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
                self.game_id = game["game_id"]
                self.game_name = game["game_name"]
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

                if new_matches:  # if new_matches is not empty
                    # create new matches if we have any
                    match_cog = self.bot.get_cog("Match")
                    for match in new_matches:
                        await match_cog.create_new_match(match)
                elif self.game_name:  # if we're not leaving queue
                    await interaction.followup.send(
                        f"Joined {self.game_name} queue", ephemeral=True
                    )
                else:
                    await interaction.followup.send("Left queue", ephemeral=True)

            except Exception as e:
                await interaction.followup.send(
                    f"Failed to join queue: {e}", ephemeral=True
                )
                # raise e

    @commands.slash_command()
    async def refresh_queues(self, ctx):
        try:
            await self.create_queues()
            await ctx.respond("Queues created", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"Failed to create queues: {e}", ephemeral=True)

    async def create_queues(self):
        channel = self.bot.get_channel(QUEUE_CHANNEL_ID)

        await channel.purge()

        # create queues for each game
        for game in self.bot.games:
            await channel.send(
                f"{game['game_name']} queue", view=self.QueueView(self.bot, game)
            )

        # also send a leave queue
        await channel.send("Leave queue", view=self.QueueView(self.bot, None))


def setup(bot):
    bot.add_cog(Queue(bot))
