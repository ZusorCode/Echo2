import logging
import discord
from discord.ext import commands
import helpers
from datetime import datetime, time, date, timedelta
from timebetween import is_time_between
import humanfriendly
import pytz


async def send_ping(channel: discord.TextChannel, role: discord.Role, user: discord.Member, message):
    # Make unofficials pingable, send the embed and ping then undo the pingable.
    await role.edit(reason="Ping Unofficials", mentionable=True)
    await channel.send(role.mention)
    embed = discord.Embed(title=f"{user.display_name} said:", description=message, colour=discord.Colour(0x358bbb))
    embed.set_footer(text="Ping by Echo", icon_url="https://cdn.discordapp.com/app-icons/581523092363411493/9f85d39eb6321ad12b2d13396c4595f5.png?size=256")

    await channel.send(embed=embed)
    await role.edit(reason="Ping Unofficials", mentionable=False)


class VetPingUnofficials(commands.Cog):
    def __init__(self, bot: commands.Bot, config: helpers.Config, log: logging.Logger):
        self.bot = bot
        self.config = config
        self.log = log
        self.log.info("Loaded Cog VetPingUnofficials")

    def embeds_contain_unofficials_ping(self, embeds: [discord.Embed]):
        """Returns true if one of the embeds has the footer Ping by Echo """
        for embed in embeds:
            self.log.warning(embed.footer.text)
            if embed.footer.text == "Ping by Echo":
                return True
        return False

    @commands.command()
    async def ping(self, ctx: commands.Context, region_name: str, *, message_for_ping):
        for region in self.config.vet_ping_unofficials:
            # Make sure the command was run in an allowed channel by a permitted person
            if region["command_channel_id"] == ctx.channel.id and region["region_name"] == region_name:
                ping_target_channel: discord.TextChannel
                ping_target_role: discord.Role
                ping_target_channel = ctx.guild.get_channel(region["ping_channel_id"])
                ping_target_role = ctx.guild.get_role(region["ping_role_id"])

                errors = []
                # Read region and times from config
                check_time = datetime.now(pytz.timezone(region["timezone_name"])).time()
                begin_time = time(region["start_ping_allow_utc"][0], region["start_ping_allow_utc"][1])
                end_time = time(region["end_ping_allow_utc"][0], region["end_ping_allow_utc"][1])

                # If we're not between time add it as an error with time until it's allowed
                if not is_time_between(check_time, begin_time, end_time):
                    if begin_time > check_time:
                        time_until_ping = datetime.combine(date.min, begin_time) - datetime.combine(date.min, check_time)
                        time_string = humanfriendly.format_timespan(time_until_ping)
                        errors.append(f"Pings are not allowed right now, you're allowed to ping in {time_string}")
                    else:
                        time_until_ping = datetime.combine(date.min, begin_time) + timedelta(days=1) - datetime.combine(date.min, check_time)
                        time_string = humanfriendly.format_timespan(time_until_ping)
                        errors.append(f"Pings are not allowed right now, you're allowed to ping in {time_string}")

                # Check if pings for the current region are on cooldown
                async for message_for_check in ping_target_channel.history(oldest_first=False):
                    # The message is relevant if it's from Echo and a previous unofficials ping
                    if message_for_check.author == self.bot.user and self.embeds_contain_unofficials_ping(message_for_check.embeds):
                        # The message is on cooldown if it's younger than the cooldown timer
                        if datetime.utcnow() - message_for_check.created_at < timedelta(seconds=region["ping_cooldown_seconds"]):
                            cooldown_time = timedelta(seconds=region['ping_cooldown_seconds']) - (datetime.utcnow() - message_for_check.created_at)
                            cooldown_time_string = humanfriendly.format_timespan(cooldown_time)
                            errors.append(f"Pings for that region are on cooldown, try in {cooldown_time_string}")

                if len(errors) == 0:
                    await ctx.message.add_reaction("👍")
                    await send_ping(ping_target_channel, ping_target_role, ctx.author, message_for_ping)
                    self.log.warning(f"{ctx.author.display_name} pinged unofficials in {region_name} with message {message_for_ping}")
                else:
                    await ctx.message.add_reaction("❌")
                    await ctx.send("Got errors:\n - " + "\n - ".join(errors))
