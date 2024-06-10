from discord.ext import commands
import discord

import requests

from discord.ext import tasks

from config import API_URL, QUEUE_CHANNEL_ID


class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.matchmake.start()

    @tasks.loop(seconds=5)
    async def matchmake(self):
        new_matches = requests.get(API_URL + "/matchmake/").json()
        if new_matches:  # if new_matches is not empty
            # create new matches if we have any
            match_cog = self.bot.get_cog("Match")
            for match in new_matches:
                await match_cog.create_new_match(match)

    @matchmake.before_loop
    async def before_matchmake(self):
        await self.bot.wait_until_ready()

    class QueueView(discord.ui.View):
        def __init__(self, bot, in_queue):
            super().__init__(timeout=None)
            self.in_queue = in_queue
            self.bot = bot

        @discord.ui.button(emoji="⛳", style=discord.ButtonStyle.secondary)
        async def button_callback(self, button, interaction):
            await interaction.response.defer(ephemeral=True)

            try:
                res = requests.patch(
                    API_URL + f"/player/{interaction.user.id}",
                    json={"in_queue": self.in_queue},
                )

                if not res.ok:
                    raise Exception(res.text)

                if self.in_queue:
                    await interaction.followup.send("Joined queue", ephemeral=True)
                else:
                    await interaction.followup.send("Left queue", ephemeral=True)

            except Exception as e:
                await interaction.followup.send(
                    f"Failed to join queue: {e}", ephemeral=True
                )
                # raise e

    async def create_queues(self):
        channel = self.bot.get_channel(QUEUE_CHANNEL_ID)

        await channel.purge()

        await channel.send("Join queue", view=self.QueueView(self.bot, True))
        await channel.send("Leave queue", view=self.QueueView(self.bot, False))


def setup(bot):
    bot.add_cog(Queue(bot))
