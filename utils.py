import discord
from discord import Embed

import requests

from config import DJANGO_AUTH_TOKEN


def request(method, url, **kwargs):
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {DJANGO_AUTH_TOKEN}"})

    if kwargs.get("headers"):
        session.headers.update(kwargs.get("headers"))

    res = session.request(method, url, **kwargs)

    if not res.ok:
        raise Exception(res.text)

    return res


class AreYouSureView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.check(interaction):
            await interaction.response.defer()
            self.value = True
            self.stop()
        else:
            await interaction.response.send_message(
                "This confirmation is not yours", ephemeral=True
            )

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.check(interaction):
            await interaction.response.defer()
            self.value = False
            self.stop()
        else:
            await interaction.response.send_message(
                "This confirmation is not yours", ephemeral=True
            )

    def check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user_id


async def are_you_sure(ctx, prompt="Are you sure?"):
    view = AreYouSureView(ctx.author.id)
    message = await ctx.respond(prompt, view=view, ephemeral=True)
    await view.wait()  # Wait for the View to stop interacting.

    return view.value, message  # True if the confirm button was pressed.


async def send_table(thread, title, cols=[], rows=[]):
    embed = Embed(title=title, color=0x00FF00)

    if cols:
        for i in range(len(cols)):
            # join 1-i with \n
            embed.add_field(
                name=cols[i][0],
                value="\n".join([cols[i][j] for j in range(1, len(cols[i]))]),
                inline=True,
            )
    elif rows:
        for i in range(len(rows[0])):
            embed.add_field(
                name=rows[0][i],
                value="\n".join([rows[j][i] for j in range(1, len(rows))]),
                inline=True,
            )

    await thread.send(embed=embed)


def generate_agree_list(match, boolean):
    # generate an array containing match.num_teams arrays containing match.players_per_team booleans
    didnt_forfeit = len([team for team in match["teams"] if not team["forfeited"]])
    return [[boolean] * match["players_per_team"] for _ in range(didnt_forfeit)]
