import discord
from discord.ext import commands


class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command()
    async def test(self, ctx):
        await ctx.send("Test command executed")

    class TestView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.select(  # the decorator that lets you specify the properties of the select menu
            placeholder="Choose a Flavor!",  # the placeholder text that will be displayed if nothing is selected
            min_values=1,  # the minimum number of values that must be selected by the users
            max_values=3,
            options=[  # the list of options from which users can choose, a required field
                discord.SelectOption(
                    label="Vanilla", description="Pick this if you like vanilla!"
                ),
                discord.SelectOption(
                    label="Chocolate", description="Pick this if you like chocolate!"
                ),
                discord.SelectOption(
                    label="Strawberry", description="Pick this if you like strawberry!"
                ),
            ],
        )
        async def select_callback(
            self, select, interaction
        ):  # the function called when the user is done selecting options
            await interaction.response.send_message(
                f"Awesome! I like {select.values[0]} too!"
            )

    @commands.slash_command()
    async def flavor(self, ctx):
        await ctx.respond("Choose a flavor!", view=self.TestView())


def setup(bot):
    bot.add_cog(Test(bot))
