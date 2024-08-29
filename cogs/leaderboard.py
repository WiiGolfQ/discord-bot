from discord.ext import commands, tasks

import requests

from config import API_URL, LEADERBOARD_CHANNEL_ID
from utils import send_table


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.send_leaderboards.start()

    @tasks.loop(minutes=15)
    async def send_leaderboards(self):
        channel = self.bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            # this needs to be here for when the channel is not in the cache
            channel = await self.bot.fetch_channel(LEADERBOARD_CHANNEL_ID)

        await channel.purge()

        for category in self.bot.categories:
            try:
                res = requests.get(API_URL + f"/leaderboard/{category['category_id']}")

                if not res.ok:
                    raise Exception(res.text)

                players_leaderboard = res.json()["results"]

                res = requests.get(
                    API_URL + f"/scores/{category['category_id']}?obsolete=true"
                )

                scores_leaderboard = res.json()["results"]

                await send_table(
                    channel,
                    f"{category['category_name']} (players leaderboard)",
                    [
                        ["__**Rank**__"]
                        + [str(item["rank"]) for item in players_leaderboard],
                        ["__**Player**__"]
                        + [item["player"]["username"] for item in players_leaderboard],
                        ["__**Elo**__"]
                        + [str(item["mu"]) for item in players_leaderboard],
                    ],
                )

                await send_table(
                    channel,
                    f"{category['category_name']} (scores leaderboard)",
                    [
                        ["__**Rank**__"]
                        + [str(item["overall_rank"]) for item in scores_leaderboard],
                        ["__**Player**__"]
                        + [item["player"]["username"] for item in scores_leaderboard],
                        ["__**Score**__"]
                        + [str(item["score_formatted"]) for item in scores_leaderboard],
                    ],
                )

            except Exception as e:
                await channel.send(
                    f"Failed to get leaderboard for {category['category_name']}: {e}"
                )


def setup(bot):
    bot.add_cog(Leaderboard(bot))
