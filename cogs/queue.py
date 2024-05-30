from discord.ext import commands
import discord

import requests

from discord.ext import tasks

from config import API_URL, QUEUE_CHANNEL_ID


class Queue(commands.Cog):
    players_queued = set()
    counter = 0

    def process_joined_player(discord_id):
        if discord_id not in Queue.players_queued:
            Queue.players_queued.add(discord_id)
            if len(Queue.players_queued) > 1:
                Queue.counter += int(25 * (0.75 ** (len(Queue.players_queued) - 1)))

    def __init__(self, bot):
        self.bot = bot
        self.matchmake.start()

    @tasks.loop(seconds=5)
    async def matchmake(self):
        if Queue.counter > 0:
            Queue.counter -= 1
            print(Queue.counter)
            return

        if len(Queue.players_queued) < 2:
            return

        new_matches = requests.get(API_URL + "/matchmake/").json()
        if new_matches:  # if new_matches is not empty
            # create new matches if we have any
            match_cog = self.bot.get_cog("Match")
            for match in new_matches:
                await match_cog.create_new_match(match)

            Queue.players_queued = set()

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
                    Queue.process_joined_player(interaction.user.id)
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

        await channel.send("Join queue", view=self.QueueView(self.bot, True))
        await channel.send("Leave queue", view=self.QueueView(self.bot, False))


def setup(bot):
    bot.add_cog(Queue(bot))
