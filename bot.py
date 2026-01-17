import os
import discord
from discord.ext import commands
import sqlite3
from datetime import timedelta

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")  # Railway secret

PERSISTENT_ROLE_IDS = [
    1454094941499293748,
    1460494191715942532
]

LOG_CHANNEL_ID = 1454114707849085095
WELCOME_CHANNEL_ID = 1453666469744476253
# ============================================

if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

# ---------- DATABASE ----------
conn = sqlite3.connect("roles.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS persistent_roles (
    user_id INTEGER,
    role_id INTEGER,
    PRIMARY KEY (user_id, role_id)
)
""")
conn.commit()

# ---------- INTENTS ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=";", intents=intents)

# ---------- LOG FUNCTION ----------
async def send_log(guild, title, description, color=discord.Color.red()):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="Moderation Logs")
        await channel.send(embed=embed)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

@bot.event
async def on_member_remove(member):
    """Save roles when user leaves"""
    for role_id in PERSISTENT_ROLE_IDS:
        role = member.guild.get_role(role_id)
        if role and role in member.roles:
            cursor.execute(
                "INSERT OR IGNORE INTO persistent_roles (user_id, role_id) VALUES (?, ?)",
                (member.id, role_id)
            )
    conn.commit()

@bot.event
async def on_member_join(member):
    # ---------- GREETING ----------
    welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        msg = await welcome_channel.send(
            f"👋 Welcome to **{member.guild.name}**, {member.mention}!"
        )
        await msg.delete(delay=10)

    # ---------- RESTORE ROLES ----------
    cursor.execute(
        "SELECT role_id FROM persistent_roles WHERE user_id = ?",
        (member.id,)
    )
    roles_to_restore = cursor.fetchall()

    restored = []
    for (role_id,) in roles_to_restore:
        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role, reason="Rejoined server – role restored")
            restored.append(role.name)

    if restored:
        await send_log(
            member.guild,
            "♻️ Roles Restored",
            f"User: {member.mention}\nRestored Roles: {', '.join(restored)}",
            discord.Color.orange()
        )

# ---------- MODERATION ----------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member}")
    await send_log(ctx.guild, "🔨 User Banned",
        f"User: {member}\nModerator: {ctx.author}\nReason: {reason}")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member}")
    await send_log(ctx.guild, "👢 User Kicked",
        f"User: {member}\nModerator: {ctx.author}\nReason: {reason}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await ctx.send(f"🔇 Muted {member} for {minutes} minutes")
    await send_log(ctx.guild, "🔇 User Muted",
        f"User: {member}\nModerator: {ctx.author}\nDuration: {minutes}m\nReason: {reason}")

# ---------- CHANNEL CONTROL ----------
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    ow = ctx.channel.overwrites_for(ctx.guild.default_role)
    ow.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send("🔒 Channel locked")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    ow = ctx.channel.overwrites_for(ctx.guild.default_role)
    ow.send_messages = None
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send("🔓 Channel unlocked")

# ---------- PURGE ----------
@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if not 1 <= amount <= 100:
        await ctx.send("❌ Amount must be 1–100")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Deleted `{len(deleted)-1}` messages")
    await msg.delete(delay=3)

# ---------- ERRORS ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid arguments.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing arguments.")
    else:
        raise error

bot.run(TOKEN)
