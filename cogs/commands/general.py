import asyncio
import logging

import discord
from discord.enums import ContentFilter
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context
from discord.ext.commands.help import Paginator
from utils import embeds
from utils.anime_search import anime_paginator, find_anime, get_pat_gif
from utils.pagination import LinePaginator
from utils.record import record_usage

log = logging.getLogger(__name__)


class General(Cog):
    """ General Commands Cog """

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.before_invoke(record_usage)
    @commands.bot_has_permissions(embed_links=True)
    @commands.command(name='profile_picture', aliases=['pfp'])
    async def pfp(self, ctx: Context, user: discord.User = None):
        """ Returns the profile picture of the invoker or the mentioned user. """

        user = user or ctx.author
        embed = embeds.make_embed(context=ctx)
        embed.set_image(url=user.avatar_url)
        await ctx.send(embed=embed)

    @commands.has_role("Staff")
    @commands.before_invoke(record_usage)
    @commands.command(name="boosttest")
    async def boosttest(self, ctx: Context):
        embed = embeds.make_embed(context=ctx, author=False)
        embed.title = "THANK YOU FOR THE BOOST!"
        embed.description = "In ornare est augue, at malesuada quam gravida id. Sed hendrerit ipsum congue, tristique nibh non, faucibus lorem. Fusce maximus risus nec rhoncus posuere. Vestibulum sapien erat, vehicula eget lorem ac, semper egestas mi. Maecenas sit amet cursus quam. Morbi non tincidunt ex. Curabitur vel pellentesque metus, vitae semper odio. Aliquam nec lectus convallis, placerat sapien ut, aliquet neque. Mauris feugiat ac arcu vel sollicitudin. Nam aliquet a sapien in auctor. Vestibulum consectetur molestie finibus."
        embed.set_image(url="https://i.imgur.com/O8R98p9.gif")
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @commands.command(name="find", aliases=["search", "findanime"])
    async def find_anime(self, ctx: Context, *, anime_name: str):
        """ Searches for Anime. """
        search_results = None
        async with ctx.typing():
            search_results = await find_anime(anime_name)

        await anime_paginator(search_results['media'], ctx)

    @commands.before_invoke(record_usage)
    @commands.command(name="userinfo", aliases=["info", "user", "whois"])
    async def info(self, ctx, user=None):
        """ Returns the user info of the invoker or the mentioned user. """
        member = None

        # Attempt to return the info of a mentioned user if the parameter was not none.
        if user is not None:
            user_strip = int(user.strip("<@!>"))
            member = ctx.message.guild.get_member(user_strip)
        # Otherwise, assume the invoker just wanted their own info and return that.
        else:
            member = ctx.message.guild.get_member(ctx.author.id)

        if member:
            embed = embeds.make_embed(
                context=ctx).set_thumbnail(url=member.avatar_url)
            embed.add_field(name="User ID", value=member.id, inline=True)
            embed.add_field(
                name="Username", value=f"{member.name}#{member.discriminator}", inline=True)
            embed.add_field(name="Nickname", value=member.nick, inline=True)
            embed.add_field(name="Joined Guild at",
                            value=member.joined_at, inline=True)
            embed.add_field(name="Joined Discord at",
                            value=member.created_at, inline=True)
            embed.add_field(name="Is Bot?", value={
                            True: "Yes", False: "No"}.get(member.bot), inline=True)

            role_list = member.roles[1:]

            role_mentions_str = ""
            for x in role_list:
                role_mentions_str += x.mention+" "

            if len(role_mentions_str) > 0:
                embed.add_field(
                    name="Roles", value=role_mentions_str, inline=False)

        else:
            raise commands.UserNotFound(member)

        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @commands.command(name="pat")
    async def pat(self, ctx, user=None):
        """ Pats the mentioned user/role. There, there. """

        embed = embeds.make_embed(context=ctx, color="gold")

        if user is not None:

            if ('&' in user):
                # Headpatting a role if the user can mention them
                user_strip = int(user.strip("<@&>"))
                role = ctx.guild.get_role(user_strip)
                nick = None
                if ctx.author.nick:
                    nick = ctx.author.nick
                else:
                    nick = ctx.author.name

                embed.title = f"{nick} just headpatted everyone in {role.name}. There, there."
                embed.description = f"Don't forget to blush, {role.mention}!"

                async with ctx.typing():
                    embed.set_image(url=get_pat_gif())
                    await asyncio.sleep(1)

                await ctx.send(embed=embed)
                return

            user_strip = int(user.strip("<@!>"))
            member = ctx.message.guild.get_member(user_strip)
            if member:
                #headpatting a user
                if member == ctx.author:
                    #Preventing users from patting themselves
                    await ctx.send("W-wait! I'll pat you, *Nyan~*!")
                    return

                nick = None
                if member.nick:
                    nick = member.nick
                else:
                    nick = member.name

                embed.title = f"{nick} just got a headpat. There, there."

                async with ctx.typing():
                    embed.set_image(url=get_pat_gif())
                    await asyncio.sleep(1)

            else:
                raise commands.UserNotFound(user)

        else:
            # No reciever was mentioned
            await ctx.send("You need to pat someone, *Nyan~*.")
            return

        await ctx.send(embed=embed)


def setup(bot: Bot) -> None:
    """ Load the General cog. """
    bot.add_cog(General(bot))
    log.info("Cog loaded: General")
