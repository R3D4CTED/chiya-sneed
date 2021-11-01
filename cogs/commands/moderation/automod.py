import json
import logging

import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import (
    create_choice,
    create_option,
    create_permission,
)
from utils import database, embeds
from utils import automod
from utils.config import config
from utils.pagination import LinePaginator
from utils.record import record_usage

# Enabling logs
log = logging.getLogger(__name__)


class AutomodCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="term",
        name="search",
        description="Searches and/or lists all the currently censored terms.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="search_term",
                option_type=3,
                description="Term to search for (supports wildcards)",
                required=False,
            ),
            create_option(
                name="censor_type",
                option_type=3,
                description="The censor type.",
                choices=[
                    create_choice(name="Exact", value="exact"),
                    create_choice(name="Substring", value="substring"),
                    create_choice(name="Regex", value="regex"),
                    create_choice(name="Links", value="links"),
                    create_choice(name="Fuzzy", value="fuzzy"),
                ],
                required=False,
            ),
        ],
        base_default_permission=False,
        base_permissions={
            config["guild_id"]: [
                create_permission(
                    config["roles"]["staff"], SlashCommandPermissionType.ROLE, True
                ),
                create_permission(
                    config["roles"]["trial_mod"], SlashCommandPermissionType.ROLE, True
                ),
            ]
        },
    )
    async def list_censors(
        self, ctx: SlashContext, search_term: str = None, censor_type: str = None
    ):
        await ctx.defer()

        censored_terms = []
        db = database.Database().get()
        censors = None
        # in the case there is a search_term specified
        if search_term:
            if censor_type:
                censors = db["censor"].find(
                    # 'ilike' is a case-insensitive search filter of table (wildcards supported)
                    # https://dataset.readthedocs.io/en/latest/queries.html#advanced-filters
                    censor_term={"ilike": search_term},
                    censor_type=censor_type,
                )
            else:
                censors = db["censor"].find(
                    censor_term={"ilike": search_term},
                )

        # if there is just censor type specified
        elif censor_type:
            censors = db["censor"].find(censor_type=censor_type)
        # if nothing is specified, list everything
        else:
            censors = db["censor"].all()

        for censor in censors:
            censor_term = censor["censor_term"]
            # If the censor is 'fuzzy' type, display the treshold value.
            if censor["censor_type"] == "fuzzy":
                censor_term = f"{censor['censor_term']} ({censor['censor_threshold']}%)"

            # Displaying whether the censor is activated or not
            enabled_emoji = (
                "<:yes:778724405333196851>"
                if censor["enabled"]
                else "<:no:778724416230129705>"
            )
            censored_term = f"**ID: {censor['id']} ** | **{censor['censor_type']}** | {enabled_emoji} \n```{censor_term}```"
            censored_terms.append(censored_term)

        embed = embeds.make_embed(
            ctx=ctx,
            title="Censored Terms",
            color="gold",
        )

        # paginating
        await LinePaginator.paginate(
            censored_terms,
            ctx=ctx,
            embed=embed,
            max_lines=5,
            max_size=2000,
            time_to_delete=30,
        )

        db.close()

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="term",
        name="add",
        description="Adds a term to the censor list.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="censor_type",
                option_type=3,
                description="The censor type",
                required=True,
                choices=[
                    create_choice(name="Exact", value="exact"),
                    create_choice(name="Substring", value="substring"),
                    create_choice(name="Regex", value="regex"),
                    create_choice(name="Links", value="links"),
                    create_choice(name="Fuzzy", value="fuzzy"),
                ],
            ),
            create_option(
                name="censor_term",
                option_type=3,
                description="The censor term.",
                required=True,
            ),
            create_option(
                name="censor_threshold",
                option_type=4,
                description="The censor treshold (only for fuzzy).",
                required=False,
            ),
        ],
        base_default_permission=False,
    )
    async def add_censor(
        self,
        ctx: SlashContext,
        censor_type: str,
        censor_term: str,
        censor_threshold: int = 0,
    ):
        await ctx.defer()

        # sanitizing input
        censor_term = censor_term.strip()
        if not censor_threshold:
            censor_threshold = 65  # default set, since this seems to work fine

        if censor_type == "fuzzy":
            # in case user enters a threshold value > 100.
            if censor_threshold > 100:
                await embeds.error_message(
                    description="Fuzziness threshold must be less than 100!", ctx=ctx
                )
                return

        db = database.Database().get()
        db["censor"].insert(
            dict(
                censor_term=censor_term,
                censor_type=censor_type,
                censor_threshold=censor_threshold,
                enabled=True,
                # Dataset seems to store json values as a string, default NULL value is problematic
                excluded_users=json.dumps(list()),
                excluded_roles=json.dumps(list()),
            )
        )

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            description=f"Censor term `{censor_term}` of type `{censor_type}` was added.",
            color="green",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="term",
        name="disable",
        description="Disables a term from the censor list.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            )
        ],
        base_default_permission=False,
    )
    async def disable_censor(self, ctx: SlashContext, id: int):
        await ctx.defer()

        db = database.Database().get()
        censor = db["censor"].find_one(id=id)

        if not censor:
            await embeds.error_message(
                ctx=ctx, description="The censor with that ID does not exist!"
            )
            return

        censor["enabled"] = False
        db["censor"].update(censor, ["id"])

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            description=f"Term `{censor['censor_term']}` of type `{censor['censor_type']}` was disabled.",
            color="red",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="term",
        name="enable",
        description="Enables a term from the censor list.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            )
        ],
        base_default_permission=False,
    )
    async def enable_censor(self, ctx: SlashContext, id: int):
        await ctx.defer()

        db = database.Database().get()
        censor = db["censor"].find_one(id=id)

        if not censor:
            await embeds.error_message(
                ctx=ctx, description="The censor with that ID does not exist!"
            )
            return

        censor["enabled"] = True
        db["censor"].update(censor, ["id"])

        db.commit()
        db.close()

        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            description=f"Term `{censor['censor_term']}` of type `{censor['censor_type']}` was enabled.",
            color="green",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="term",
        name="delete",
        description="Deletes a term from the censor list.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            )
        ],
        base_default_permission=False,
    )
    async def delete_censor(self, ctx: SlashContext, id: int):
        await ctx.defer()

        db = database.Database().get()
        censor = db["censor"].find_one(id=id)

        if not censor:
            await embeds.error_message(
                ctx=ctx, description="The censor with that ID does not exist!"
            )
            return

        db["censor"].delete(id=id)

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            description=f"Term `{censor['censor_term']}` of type `{censor['censor_type']}` was deleted.",
            color="red",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="user_exclusion",
        name="add",
        description="Excludes a user from an automod listing.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            ),
            create_option(
                name="excluded_user",
                description="The member that will be excluded.",
                option_type=6,
                required=True,
            ),
        ],
        base_default_permission=False,
    )
    async def exclude_user_from_automod(
        self, ctx: SlashContext, id: int, excluded_user: discord.User
    ):
        await ctx.defer()
        user_id = excluded_user.id

        db = database.Database().get()

        table = db["censor"]

        censor = table.find_one(id=id)
        if not censor:
            await embeds.error_message(
                ctx=ctx, description="Could not find a censor with that ID!"
            )
            return

        # initializing, in the case the List in the DB is empty
        excluded_users = list()
        if censor["excluded_users"]:
            # The JSON List is stored as a string in the DB, so converting that to a List first
            excluded_users = json.loads(censor["excluded_users"])

        excluded_users.append(user_id)
        censor["excluded_users"] = json.dumps(excluded_users)
        table.update(censor, ["id"])

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            title="User Excluded",
            description=f"User {excluded_user.mention} was excluded from automod for the term `{censor['censor_term']}` of type `{censor['censor_type']}`.",
            color="green",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="user_exclusion",
        name="remove",
        description="Removes the exclusion of a user from an automod listing.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            ),
            create_option(
                name="unexcluded_user",
                description="The member whose exclusion will be removed.",
                option_type=6,
                required=True,
            ),
        ],
        base_default_permission=False,
    )
    async def unexclude_user_from_automod(
        self, ctx: SlashContext, id: int, unexcluded_user: discord.User
    ):
        await ctx.defer()
        user_id = unexcluded_user.id

        db = database.Database().get()

        table = db["censor"]

        censor = table.find_one(id=id)
        if not censor:
            await embeds.error_message(
                ctx=ctx, description="Could not find a censor with that ID!"
            )
            return

        excluded_users = list()
        if censor["excluded_users"]:
            # The JSON List is stored as a string in the DB, so converting that to a List first
            excluded_users = json.loads(censor["excluded_users"])

        if not user_id in excluded_users:
            await embeds.error_message(
                ctx=ctx,
                description=f"The user {unexcluded_user.mention} isn't excluded!",
            )
            return

        excluded_users.remove(user_id)
        censor["excluded_users"] = json.dumps(excluded_users)
        table.update(censor, ["id"])

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            title="User Exclusion Removed.",
            description=f"User {unexcluded_user.mention}'s exclusion from automod for the term `{censor['censor_term']}` of type `{censor['censor_type']}` was removed.",
            color="red",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="role_exclusion",
        name="add",
        description="Excludes a role from an automod listing.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            ),
            create_option(
                name="excluded_role",
                description="The role that will be excluded.",
                option_type=8,
                required=True,
            ),
        ],
        base_default_permission=False,
    )
    async def exclude_role_from_automod(
        self, ctx: SlashContext, id: int, excluded_role: discord.Role
    ):
        await ctx.defer()
        role_id = excluded_role.id

        db = database.Database().get()

        table = db["censor"]

        censor = table.find_one(id=id)
        if not censor:
            await embeds.error_message(
                ctx=ctx, description="Could not find a censor with that ID!"
            )
            return

        excluded_roles = list()
        if censor["excluded_roles"]:
            excluded_roles = json.loads(censor["excluded_roles"])

        excluded_roles.append(role_id)
        censor["excluded_roles"] = json.dumps(excluded_roles)
        table.update(censor, ["id"])

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            title="Role Excluded",
            description=f"Role {excluded_role.mention} was excluded from automod for the term `{censor['censor_term']}` of type `{censor['censor_type']}`.",
            color="green",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        subcommand_group="role_exclusion",
        name="remove",
        description="Removes the exclusion of a role from an automod listing.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            ),
            create_option(
                name="unexcluded_role",
                description="The role whose exclusion will be removed.",
                option_type=8,
                required=True,
            ),
        ],
        base_default_permission=False,
    )
    async def unexclude_role_from_automod(
        self, ctx: SlashContext, id: int, unexcluded_role: discord.Role
    ):
        await ctx.defer()
        role_id = unexcluded_role.id

        db = database.Database().get()

        table = db["censor"]

        censor = table.find_one(id=id)
        if not censor:
            await embeds.error_message(
                ctx=ctx, description="Could not find a censor with that ID!"
            )
            return

        excluded_roles = list()
        if censor["excluded_roles"]:
            excluded_roles = json.loads(censor["excluded_roles"])

        if not role_id in excluded_roles:
            await embeds.error_message(
                ctx=ctx,
                description=f"The role {unexcluded_role.mention} isn't excluded!",
            )
            return

        excluded_roles.remove(role_id)
        censor["excluded_roles"] = json.dumps(excluded_roles)
        table.update(censor, ["id"])

        db.commit()
        db.close()
        # refresh the censor cache, so that the term is updated in the local copy
        automod.refresh_censor_cache()

        embed = embeds.make_embed(
            ctx=ctx,
            title="Role Exclusion Removed",
            description=f"Role {unexcluded_role.mention}'s exclusion was removed from automod for the term `{censor['censor_term']}` of type `{censor['censor_type']}`.",
            color="red",
        )
        await ctx.send(embed=embed)

    @commands.before_invoke(record_usage)
    @cog_ext.cog_subcommand(
        base="automod",
        name="details",
        description="Displays the advanced details for an automod listing.",
        guild_ids=[config["guild_id"]],
        options=[
            create_option(
                name="id",
                option_type=4,
                description="ID of the censored term.",
                required=True,
            ),
        ],
        base_default_permission=True,
    )
    async def automod_details(self, ctx: SlashContext, id: int):
        await ctx.defer()

        db = database.Database().get()
        table = db["censor"]
        censor = table.find_one(id=id)
        if not censor:
            await embeds.error_message(
                ctx=ctx, description="Could not find a censor with that ID!"
            )
            return

        embed = embeds.make_embed(ctx=ctx, title="Automod Listing details")
        enabled_emoji = (
            "<:yes:778724405333196851>"
            if censor["enabled"]
            else "<:no:778724416230129705>"
        )
        embed.description = f"**ID:** {censor['id']} | **Censor Term:** `{censor['censor_term']}` | {enabled_emoji} "

        excluded_users = json.loads(censor["excluded_users"])
        # only display excluded users if there are any exclusions
        if excluded_users:
            excluded_users = ""
            for user_id in json.loads(censor["excluded_users"]):
                excluded_users += f"<@{user_id}> "
            embed.add_field(name="Excluded Users:", value=excluded_users, inline=False)

        excluded_roles = json.loads(censor["excluded_roles"])
        # only display excluded roles if there are exclusions
        if excluded_roles:
            excluded_roles = ""
            for role_id in json.loads(censor["excluded_roles"]):
                excluded_roles += f"<@&{role_id}> "
            embed.add_field(name="Excluded Roles:", value=excluded_roles, inline=False)

        await ctx.send(embed=embed)


def setup(bot) -> None:
    bot.add_cog(AutomodCog(bot))
    log.info("Cog loaded: AutomodCog")
